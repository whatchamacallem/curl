/***************************************************************************
 *                                  _   _ ____  _
 *  Project                     ___| | | |  _ \| |
 *                             / __| | | | |_) | |
 *                            | (__| |_| |  _ <| |___
 *                             \___|\___/|_| \_\_____|
 *
 * Copyright (C) Daniel Stenberg, <daniel@haxx.se>, et al.
 *
 * This software is licensed as described in the file COPYING, which
 * you should have received as part of this distribution. The terms
 * are also available at https://curl.se/docs/copyright.html.
 *
 * You may opt to use, copy, modify, merge, publish, distribute and/or sell
 * copies of the Software, and permit persons to whom the Software is
 * furnished to do so, under the terms of the COPYING file.
 *
 * This software is distributed on an "AS IS" basis, WITHOUT WARRANTY OF ANY
 * KIND, either express or implied.
 *
 * SPDX-License-Identifier: curl
 *
 ***************************************************************************/
/* Escape and unescape URL encoding in strings. The functions return a new
 * allocated string or NULL if an error occurred. */
#include "curl_setup.h"

struct Curl_easy;

#include "urldata.h"
#include "escape.h"
#include "curlx/strparse.h"
#include "curl_printf.h"

#ifdef USE_SIMD
#include <immintrin.h>
#if defined(__AVX512BW__) && defined(__AVX512VL__)
#define CURL_SIMD_AVX_512 1
#elif defined(__AVX2__)
#define CURL_SIMD_AVX2 1
#endif
#endif

/* for ABI-compatibility with previous versions */
char *curl_escape(const char *string, int length)
{
  return curl_easy_escape(NULL, string, length);
}

/* for ABI-compatibility with previous versions */
char *curl_unescape(const char *string, int length)
{
  return curl_easy_unescape(NULL, string, length, NULL);
}

#define NOPE 0xff
#define _OK_ 0x1f /* octet not needing encoding but not a hexadecimal
                     character */

static const unsigned char hextable[256] = {
  NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, /* 00 */
  NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, /* 08 */
  NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, /* 10 */
  NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, /* 18 */
  NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, /* 20 */
  NOPE, NOPE, NOPE, NOPE, NOPE, _OK_, _OK_, NOPE, /* 28 */
  0,    1,    2,    3,    4,    5,    6,    7,    /* 30 */
  8,    9,    NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, /* 38 */
  NOPE, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f, _OK_, /* 40 */
  _OK_, _OK_, _OK_, _OK_, _OK_, _OK_, _OK_, _OK_, /* 48 */
  _OK_, _OK_, _OK_, _OK_, _OK_, _OK_, _OK_, _OK_, /* 50 */
  _OK_, _OK_, _OK_, NOPE, NOPE, NOPE, NOPE, _OK_, /* 58 */
  NOPE, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f, _OK_, /* 60 */
  _OK_, _OK_, _OK_, _OK_, _OK_, _OK_, _OK_, _OK_, /* 68 */
  _OK_, _OK_, _OK_, _OK_, _OK_, _OK_, _OK_, _OK_, /* 70 */
  _OK_, _OK_, _OK_, NOPE, NOPE, NOPE, _OK_, NOPE, /* 78 */
  NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, /* 80 - not ASCII */
  NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE,
  NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE,
  NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE,
  NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE,
  NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE,
  NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE,
  NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE,
  NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE,
  NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE,
  NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE,
  NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE,
  NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE,
  NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE,
  NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE,
  NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE, NOPE
};

/*
 * urldecode_run() decodes a run of consecutive "%XX" triplets at the start
 * of 'in'. It consumes as many triplets as fit in one step: zero if the
 * first bytes are not a complete, valid run of triplets, or if 'inlen' is
 * shorter than what one step loads (the vector bodies load a few bytes
 * more than they consume; the scalar code handles the tail).
 *
 * Returns the number of input bytes consumed, always a multiple of three.
 * The decoded bytes are stored to 'out'. If any decoded byte is below
 * 'reject_limit', 'rejected' is set to TRUE and nothing is consumed; the
 * caller then fails the whole decode exactly like the scalar path does.
 *
 * Never reads past in[inlen - 1].
 *
 * There are three bodies, selected at compile time: AVX-512 (BW + VL),
 * AVX2 and plain C. They must produce identical results. The C body is
 * also used when USE_SIMD is set but the compiler targets neither.
 */

#ifdef CURL_SIMD_AVX_512

#define URLDECODE_RUN_TRIPLETS 20

/* Two 32 byte loads at offsets 0 and 30 make each 256 bit half hold ten
   whole triplets, so no triplet straddles a 128 bit lane boundary and the
   lane local vpshufb controls below are the same for all four lanes.
   Within each half, the low lane holds triplets 0-4 at bytes 0-14 and the
   high lane holds triplets 5-9 at bytes 16-29. The high nibble control
   gathers bytes 1, 4, ..., the low nibble control bytes 2, 5, ...; each
   control places its five digits at the output positions of its triplets
   and zeroes the rest, so the two lanes OR together into ten bytes. */
static const uint8_t urldecode_hi_ctrl[64] = {
  1, 4, 7, 10, 13, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80,
  0x80, 0x80,
  0x80, 0x80, 0x80, 0x80, 0x80, 0, 3, 6, 9, 12, 0x80, 0x80, 0x80, 0x80,
  0x80, 0x80,
  1, 4, 7, 10, 13, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80,
  0x80, 0x80,
  0x80, 0x80, 0x80, 0x80, 0x80, 0, 3, 6, 9, 12, 0x80, 0x80, 0x80, 0x80,
  0x80, 0x80
};
static const uint8_t urldecode_lo_ctrl[64] = {
  2, 5, 8, 11, 14, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80,
  0x80, 0x80,
  0x80, 0x80, 0x80, 0x80, 0x80, 1, 4, 7, 10, 13, 0x80, 0x80, 0x80, 0x80,
  0x80, 0x80,
  2, 5, 8, 11, 14, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80,
  0x80, 0x80,
  0x80, 0x80, 0x80, 0x80, 0x80, 1, 4, 7, 10, 13, 0x80, 0x80, 0x80, 0x80,
  0x80, 0x80
};

/* bit i set when byte i is a '%' in a run of ten triplets per half */
#define URLDECODE_PCT_MASK 0x0924924909249249ULL
/* bit i set when byte i is a hex digit in a run of ten triplets per half */
#define URLDECODE_HEX_MASK 0x36db6db636db6db6ULL
/* bits 30, 31, 62 and 63 are not part of any triplet */
#define URLDECODE_CARE_MASK 0x3fffffff3fffffffULL

static CURL_INLINE size_t urldecode_run(const char *in, size_t inlen,
                                        uint8_t *out, uint8_t reject_limit,
                                        bool *rejected)
{
  __m512i v, d, a, nib, hi, lo;
  __m256i h, r;
  __mmask64 kdigit, kletter;

  /* 62 bytes are read: 30 triplets bytes from each of the two loads */
  if(inlen < 62)
    return 0;

  v = _mm512_inserti64x4(
    _mm512_castsi256_si512(
      _mm256_loadu_si256((const __m256i *)(const void *)in)),
    _mm256_loadu_si256((const __m256i *)(const void *)(in + 30)), 1);

  /* every third byte starting at zero must be a '%' */
  if((_mm512_cmpeq_epi8_mask(v, _mm512_set1_epi8('%')) &
      URLDECODE_CARE_MASK) != URLDECODE_PCT_MASK)
    return 0;

  /* classify every byte as a hex digit: d = c - '0' is a digit when
     d <= 9, a = (c | 0x20) - 'a' is a letter when a <= 5 */
  d = _mm512_sub_epi8(v, _mm512_set1_epi8('0'));
  a = _mm512_sub_epi8(_mm512_or_si512(v, _mm512_set1_epi8(0x20)),
                      _mm512_set1_epi8('a'));
  kdigit = _mm512_cmple_epu8_mask(d, _mm512_set1_epi8(9));
  kletter = _mm512_cmple_epu8_mask(a, _mm512_set1_epi8(5));
  if(((kdigit | kletter) & URLDECODE_CARE_MASK) != URLDECODE_HEX_MASK)
    return 0;

  /* nibble value of every digit byte */
  nib = _mm512_mask_blend_epi8(kdigit, _mm512_add_epi8(a,
                                                       _mm512_set1_epi8(10)),
                               d);

  /* gather the high and low nibbles of each triplet, lane by lane */
  hi = _mm512_shuffle_epi8(nib, _mm512_loadu_si512(urldecode_hi_ctrl));
  lo = _mm512_shuffle_epi8(nib, _mm512_loadu_si512(urldecode_lo_ctrl));

  /* OR the lanes of each half: 128 bit lanes 0|1 and 2|3 */
  h = _mm256_or_si256(
    _mm512_castsi512_si256(_mm512_shuffle_i64x2(hi, hi, 0x08)),
    _mm512_castsi512_si256(_mm512_shuffle_i64x2(hi, hi, 0x0d)));
  r = _mm256_or_si256(
    _mm512_castsi512_si256(_mm512_shuffle_i64x2(lo, lo, 0x08)),
    _mm512_castsi512_si256(_mm512_shuffle_i64x2(lo, lo, 0x0d)));

  /* the high nibble is at most 0x0f, so the shift stays within the byte */
  r = _mm256_or_si256(_mm256_slli_epi16(h, 4), r);

  /* lane 0 holds the first ten bytes, lane 1 the next ten */
  if(_mm256_cmplt_epu8_mask(r, _mm256_set1_epi8((char)reject_limit)) &
     0x03ff03ffU) {
    *rejected = TRUE;
    return 0;
  }

  _mm_mask_storeu_epi8(out, 0x03ff, _mm256_castsi256_si128(r));
  _mm_mask_storeu_epi8(out + 10, 0x03ff, _mm256_extracti128_si256(r, 1));
  return 3 * URLDECODE_RUN_TRIPLETS;
}

#elif defined(CURL_SIMD_AVX2)

#define URLDECODE_RUN_TRIPLETS 10

/* vpshufb only moves bytes within each 128 bit lane. The low lane holds
   triplets 0-4 at bytes 0-14, the high lane holds triplets 5-9 at bytes
   16-29. The high nibble control gathers bytes 1, 4, ..., the low nibble
   control bytes 2, 5, ...; each control places its five digits at the
   output positions of its triplets and zeroes the rest, so the two lanes
   OR together into ten bytes. */
static const uint8_t urldecode_hi_ctrl[32] = {
  1, 4, 7, 10, 13, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80,
  0x80, 0x80,
  0x80, 0x80, 0x80, 0x80, 0x80, 0, 3, 6, 9, 12, 0x80, 0x80, 0x80, 0x80,
  0x80, 0x80
};
static const uint8_t urldecode_lo_ctrl[32] = {
  2, 5, 8, 11, 14, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80,
  0x80, 0x80,
  0x80, 0x80, 0x80, 0x80, 0x80, 1, 4, 7, 10, 13, 0x80, 0x80, 0x80, 0x80,
  0x80, 0x80
};

/* bit i set when byte i is a '%' in a run of ten triplets */
#define URLDECODE_PCT_MASK 0x09249249U
/* bit i set when byte i is a hex digit in a run of ten triplets */
#define URLDECODE_HEX_MASK 0x36db6db6U
/* bits 30 and 31 are not part of any triplet */
#define URLDECODE_CARE_MASK 0x3fffffffU

static CURL_INLINE size_t urldecode_run(const char *in, size_t inlen,
                                        uint8_t *out, uint8_t reject_limit,
                                        bool *rejected)
{
  __m256i v, d, a, digit, letter, nib, hi, lo;
  __m128i r;
  unsigned int m;
  uint16_t tail;

  if(inlen < 32)
    return 0;

  v = _mm256_loadu_si256((const __m256i *)(const void *)in);

  /* every third byte starting at zero must be a '%' */
  m = (unsigned int)_mm256_movemask_epi8(
    _mm256_cmpeq_epi8(v, _mm256_set1_epi8('%')));
  if((m & URLDECODE_CARE_MASK) != URLDECODE_PCT_MASK)
    return 0;

  /* classify every byte as a hex digit: d = c - '0' is a digit when
     d <= 9, a = (c | 0x20) - 'a' is a letter when a <= 5. AVX2 has no
     unsigned compare, max_epu8(x, n) == n is the x <= n idiom. */
  d = _mm256_sub_epi8(v, _mm256_set1_epi8('0'));
  a = _mm256_sub_epi8(_mm256_or_si256(v, _mm256_set1_epi8(0x20)),
                      _mm256_set1_epi8('a'));
  digit = _mm256_cmpeq_epi8(_mm256_max_epu8(d, _mm256_set1_epi8(9)),
                            _mm256_set1_epi8(9));
  letter = _mm256_cmpeq_epi8(_mm256_max_epu8(a, _mm256_set1_epi8(5)),
                             _mm256_set1_epi8(5));
  m = (unsigned int)_mm256_movemask_epi8(_mm256_or_si256(digit, letter));
  if((m & URLDECODE_CARE_MASK) != URLDECODE_HEX_MASK)
    return 0;

  /* nibble value of every digit byte */
  nib = _mm256_blendv_epi8(_mm256_add_epi8(a, _mm256_set1_epi8(10)), d,
                           digit);

  /* gather the high and low nibbles of each triplet, lane by lane, then
     OR the two lanes into one ten byte result */
  hi = _mm256_shuffle_epi8(
    nib, _mm256_loadu_si256((const __m256i *)(const void *)
                            urldecode_hi_ctrl));
  lo = _mm256_shuffle_epi8(
    nib, _mm256_loadu_si256((const __m256i *)(const void *)
                            urldecode_lo_ctrl));
  r = _mm_or_si128(_mm256_castsi256_si128(hi),
                   _mm256_extracti128_si256(hi, 1));
  /* the high nibble is at most 0x0f, so the shift stays within the byte */
  r = _mm_slli_epi16(r, 4);
  r = _mm_or_si128(r, _mm_or_si128(_mm256_castsi256_si128(lo),
                                   _mm256_extracti128_si256(lo, 1)));

  /* a byte is accepted when max(byte, limit) == byte */
  m = (unsigned int)_mm_movemask_epi8(
    _mm_cmpeq_epi8(_mm_max_epu8(r, _mm_set1_epi8((char)reject_limit)), r));
  if((m & 0x03ffU) != 0x03ffU) {
    *rejected = TRUE;
    return 0;
  }

  _mm_storel_epi64((__m128i *)(void *)out, r);
  tail = (uint16_t)_mm_extract_epi16(r, 4);
  memcpy(out + 8, &tail, sizeof(tail));
  return 3 * URLDECODE_RUN_TRIPLETS;
}

#else /* plain C */

#define URLDECODE_RUN_TRIPLETS 10

static CURL_INLINE size_t urldecode_run(const char *in, size_t inlen,
                                        uint8_t *out, uint8_t reject_limit,
                                        bool *rejected)
{
  uint8_t tmp[URLDECODE_RUN_TRIPLETS];
  size_t i;

  if(inlen < 3 * URLDECODE_RUN_TRIPLETS)
    return 0;

  for(i = 0; i < URLDECODE_RUN_TRIPLETS; i++) {
    const char *t = &in[i * 3];
    uint8_t h1 = hextable[(uint8_t)t[1]];
    uint8_t h2 = hextable[(uint8_t)t[2]];
    if((t[0] != '%') || ((h1 | h2) & 0xf0))
      return 0;
    tmp[i] = (uint8_t)((h1 << 4) | h2);
  }

  for(i = 0; i < URLDECODE_RUN_TRIPLETS; i++) {
    if(tmp[i] < reject_limit) {
      *rejected = TRUE;
      return 0;
    }
  }

  memcpy(out, tmp, sizeof(tmp));
  return 3 * URLDECODE_RUN_TRIPLETS;
}

#endif /* CURL_SIMD_AVX_512 / CURL_SIMD_AVX2 / C */

#ifdef UNITTESTS
/* @unittest 1688 */
UNITTEST size_t urldecode_run_unit(const char *in, size_t inlen,
                                   uint8_t *out, uint8_t reject_limit,
                                   bool *rejected);
UNITTEST size_t urldecode_run_unit(const char *in, size_t inlen,
                                   uint8_t *out, uint8_t reject_limit,
                                   bool *rejected)
{
  return urldecode_run(in, inlen, out, reject_limit, rejected);
}
#endif

/* Escapes for URL the given unescaped string of given length.
 * 'data' is ignored since 7.82.0.
 */
char *curl_easy_escape(CURL *curl, const char *string, int length)
{
  size_t len;
  const char *f = string;
  size_t nappend = 0;
  char *target;
  char *encoded;
  (void)curl;

  if(!string || (length < 0))
    return NULL;

  len = (length ? (size_t)length : strlen(string));
  if(!len)
    return curlx_strdup("");

  if(len > SIZE_MAX / 16)
    return NULL;

  encoded = target = curlx_malloc((len * 3) + 1);
  if(!target)
    return NULL;

  while(len--) {
    uint8_t in = (uint8_t)*string++;

    if(!(hextable[in] & 0x80))
      /* append this */
      nappend++;
    else {
      if(nappend) {
        memcpy(target, f, nappend);
        target += nappend;
        nappend = 0;
      }
      f = string;
      /* encode it */
      target[0] = '%';
      target[1] = Curl_udigits[in >> 4];
      target[2] = Curl_udigits[in & 0x0F];
      target += 3;
    }
  }
  if(nappend) {
    memcpy(target, f, nappend);
    target += nappend;
  }
  *target = '\0'; /* null terminate */

  return encoded;
}

/*
 * Curl_urldecode() URL decodes the given string.
 *
 * Returns a pointer to a malloced string in *ostring with length given in
 * *olen. If length == 0, the length is assumed to be strlen(string).
 *
 * ctrl options:
 * - REJECT_NADA: accept everything
 * - REJECT_CTRL: rejects control characters (byte codes lower than 32) in
 *                the data
 * - REJECT_ZERO: rejects decoded zero bytes
 *
 * The values for the enum starts at 2, to make the assert detect legacy
 * invokes that used TRUE/FALSE (0 and 1).
 */

CURLcode Curl_urldecode(const char *string, size_t length,
                        char **ostring, size_t *olen,
                        enum urlreject ctrl)
{
  size_t alloc;
  char *ns;
  uint8_t reject_limit;

  DEBUGASSERT(string);
  DEBUGASSERT(ctrl >= REJECT_NADA); /* crash on TRUE/FALSE */

  alloc = (length ? length : strlen(string));
  ns = curlx_malloc(alloc + 1);

  if(!ns)
    return CURLE_OUT_OF_MEMORY;

  /* store output string */
  *ostring = ns;

  reject_limit = (ctrl == REJECT_CTRL) ? 0x20 :
    (ctrl == REJECT_ZERO) ? 1 : 0;

  while(alloc) {
    uint8_t in;

    if(*string == '%') {
      bool rejected = FALSE;
      size_t used = urldecode_run(string, alloc, (uint8_t *)ns,
                                  reject_limit, &rejected);
      if(rejected)
        goto error;
      if(used) {
        ns += used / 3;
        string += used;
        alloc -= used;
        continue;
      }
      if(alloc > 2) {
        uint8_t h1 = hextable[(uint8_t)string[1]];
        uint8_t h2 = hextable[(uint8_t)string[2]];
        if(!((h1 | h2) & 0xf0)) {
          in = (uint8_t)((h1 << 4) | h2);
          string += 3;
          alloc -= 3;
          if(in < reject_limit)
            goto error;
          *ns++ = (char)in;
          continue;
        }
      }
      in = '%';
      string++;
      alloc--;
      *ns++ = (char)in;
      continue;
    }
    else {
      const char *p = memchr(string + 1, '%', alloc - 1);
      size_t n = p ? (size_t)(p - string) : alloc;

      if(reject_limit) {
        if(reject_limit == 1) {
          if(memchr(string, 0, n))
            goto error;
        }
        else {
          size_t i;
          for(i = 0; i < n; i++) {
            if((uint8_t)string[i] < 0x20)
              goto error;
          }
        }
      }

      memcpy(ns, string, n);
      ns += n;
      string += n;
      alloc -= n;
    }
  }
  *ns = 0; /* terminate it */

  if(olen)
    /* store output size */
    *olen = (size_t)(ns - *ostring);

  return CURLE_OK;
error:
  curlx_safefree(*ostring);
  return CURLE_URL_MALFORMAT;
}

/*
 * Unescapes the given URL escaped string of given length. Returns a
 * pointer to a malloced string with length given in *olen.
 * If length == 0, the length is assumed to be strlen(string).
 * If olen == NULL, no output length is stored.
 * 'data' is ignored since 7.82.0.
 */
char *curl_easy_unescape(CURL *curl, const char *string, int inlength,
                         int *outlength)
{
  char *str = NULL;
  (void)curl;
  if(string && (inlength >= 0)) {
    size_t inputlen = (size_t)inlength;
    size_t outputlen;
    CURLcode res = Curl_urldecode(string, inputlen, &str, &outputlen,
                                  REJECT_NADA);
    if(res)
      return NULL;

    if(outlength) {
      if(outputlen <= (size_t)INT_MAX)
        *outlength = curlx_uztosi(outputlen);
      else
        /* too large to return in an int, fail! */
        curlx_safefree(str);
    }
  }
  return str;
}

/* For operating systems/environments that use different malloc/free
   systems for the app and for this library, we provide a free that uses
   the library's memory system */
void curl_free(void *p)
{
  curlx_free(p);
}

/*
 * Curl_hexencode()
 *
 * Converts binary input to lowercase hex-encoded ASCII output.
 * null-terminated.
 */
void Curl_hexencode(const unsigned char *src, size_t len, /* input length */
                    unsigned char *out, size_t olen) /* output buffer size */
{
  DEBUGASSERT(src && len && (olen >= 3));
  if(src && len && (olen >= 3)) {
    while(len-- && (olen >= 3)) {
      out[0] = Curl_ldigits[*src >> 4];
      out[1] = Curl_ldigits[*src & 0x0F];
      ++src;
      out += 2;
      olen -= 2;
    }
    *out = 0;
  }
  else if(olen)
    *out = 0;
}

/* Curl_hexbyte
 *
 * Output a single unsigned char as a two-digit UPPERCASE hex number.
 */
void Curl_hexbyte(unsigned char *dest, /* must fit two bytes */
                  unsigned char val)
{
  dest[0] = Curl_udigits[val >> 4];
  dest[1] = Curl_udigits[val & 0x0F];
}
