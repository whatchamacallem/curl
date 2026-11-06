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

#ifdef USE_AVX2
#include <immintrin.h>
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

static const char hexpairs[][2] = {
  {'0', '0'}, {'0', '1'}, {'0', '2'}, {'0', '3'},
  {'0', '4'}, {'0', '5'}, {'0', '6'}, {'0', '7'},
  {'0', '8'}, {'0', '9'}, {'0', 'A'}, {'0', 'B'},
  {'0', 'C'}, {'0', 'D'}, {'0', 'E'}, {'0', 'F'},
  {'1', '0'}, {'1', '1'}, {'1', '2'}, {'1', '3'},
  {'1', '4'}, {'1', '5'}, {'1', '6'}, {'1', '7'},
  {'1', '8'}, {'1', '9'}, {'1', 'A'}, {'1', 'B'},
  {'1', 'C'}, {'1', 'D'}, {'1', 'E'}, {'1', 'F'},
  {'2', '0'}, {'2', '1'}, {'2', '2'}, {'2', '3'},
  {'2', '4'}, {'2', '5'}, {'2', '6'}, {'2', '7'},
  {'2', '8'}, {'2', '9'}, {'2', 'A'}, {'2', 'B'},
  {'2', 'C'}, {'2', 'D'}, {'2', 'E'}, {'2', 'F'},
  {'3', '0'}, {'3', '1'}, {'3', '2'}, {'3', '3'},
  {'3', '4'}, {'3', '5'}, {'3', '6'}, {'3', '7'},
  {'3', '8'}, {'3', '9'}, {'3', 'A'}, {'3', 'B'},
  {'3', 'C'}, {'3', 'D'}, {'3', 'E'}, {'3', 'F'},
  {'4', '0'}, {'4', '1'}, {'4', '2'}, {'4', '3'},
  {'4', '4'}, {'4', '5'}, {'4', '6'}, {'4', '7'},
  {'4', '8'}, {'4', '9'}, {'4', 'A'}, {'4', 'B'},
  {'4', 'C'}, {'4', 'D'}, {'4', 'E'}, {'4', 'F'},
  {'5', '0'}, {'5', '1'}, {'5', '2'}, {'5', '3'},
  {'5', '4'}, {'5', '5'}, {'5', '6'}, {'5', '7'},
  {'5', '8'}, {'5', '9'}, {'5', 'A'}, {'5', 'B'},
  {'5', 'C'}, {'5', 'D'}, {'5', 'E'}, {'5', 'F'},
  {'6', '0'}, {'6', '1'}, {'6', '2'}, {'6', '3'},
  {'6', '4'}, {'6', '5'}, {'6', '6'}, {'6', '7'},
  {'6', '8'}, {'6', '9'}, {'6', 'A'}, {'6', 'B'},
  {'6', 'C'}, {'6', 'D'}, {'6', 'E'}, {'6', 'F'},
  {'7', '0'}, {'7', '1'}, {'7', '2'}, {'7', '3'},
  {'7', '4'}, {'7', '5'}, {'7', '6'}, {'7', '7'},
  {'7', '8'}, {'7', '9'}, {'7', 'A'}, {'7', 'B'},
  {'7', 'C'}, {'7', 'D'}, {'7', 'E'}, {'7', 'F'},
  {'8', '0'}, {'8', '1'}, {'8', '2'}, {'8', '3'},
  {'8', '4'}, {'8', '5'}, {'8', '6'}, {'8', '7'},
  {'8', '8'}, {'8', '9'}, {'8', 'A'}, {'8', 'B'},
  {'8', 'C'}, {'8', 'D'}, {'8', 'E'}, {'8', 'F'},
  {'9', '0'}, {'9', '1'}, {'9', '2'}, {'9', '3'},
  {'9', '4'}, {'9', '5'}, {'9', '6'}, {'9', '7'},
  {'9', '8'}, {'9', '9'}, {'9', 'A'}, {'9', 'B'},
  {'9', 'C'}, {'9', 'D'}, {'9', 'E'}, {'9', 'F'},
  {'A', '0'}, {'A', '1'}, {'A', '2'}, {'A', '3'},
  {'A', '4'}, {'A', '5'}, {'A', '6'}, {'A', '7'},
  {'A', '8'}, {'A', '9'}, {'A', 'A'}, {'A', 'B'},
  {'A', 'C'}, {'A', 'D'}, {'A', 'E'}, {'A', 'F'},
  {'B', '0'}, {'B', '1'}, {'B', '2'}, {'B', '3'},
  {'B', '4'}, {'B', '5'}, {'B', '6'}, {'B', '7'},
  {'B', '8'}, {'B', '9'}, {'B', 'A'}, {'B', 'B'},
  {'B', 'C'}, {'B', 'D'}, {'B', 'E'}, {'B', 'F'},
  {'C', '0'}, {'C', '1'}, {'C', '2'}, {'C', '3'},
  {'C', '4'}, {'C', '5'}, {'C', '6'}, {'C', '7'},
  {'C', '8'}, {'C', '9'}, {'C', 'A'}, {'C', 'B'},
  {'C', 'C'}, {'C', 'D'}, {'C', 'E'}, {'C', 'F'},
  {'D', '0'}, {'D', '1'}, {'D', '2'}, {'D', '3'},
  {'D', '4'}, {'D', '5'}, {'D', '6'}, {'D', '7'},
  {'D', '8'}, {'D', '9'}, {'D', 'A'}, {'D', 'B'},
  {'D', 'C'}, {'D', 'D'}, {'D', 'E'}, {'D', 'F'},
  {'E', '0'}, {'E', '1'}, {'E', '2'}, {'E', '3'},
  {'E', '4'}, {'E', '5'}, {'E', '6'}, {'E', '7'},
  {'E', '8'}, {'E', '9'}, {'E', 'A'}, {'E', 'B'},
  {'E', 'C'}, {'E', 'D'}, {'E', 'E'}, {'E', 'F'},
  {'F', '0'}, {'F', '1'}, {'F', '2'}, {'F', '3'},
  {'F', '4'}, {'F', '5'}, {'F', '6'}, {'F', '7'},
  {'F', '8'}, {'F', '9'}, {'F', 'A'}, {'F', 'B'},
  {'F', 'C'}, {'F', 'D'}, {'F', 'E'}, {'F', 'F'}
};

/*
 * urldecode_block() decodes URLDECODE_BLOCK_TRIPLETS consecutive "%XX"
 * triplets at the start of 'in' into 'out'. It returns TRUE when all of
 * them were well-formed and FALSE otherwise, in which case 'out' may have
 * been partially written and the caller falls back to the one triplet at a
 * time code. The caller checks the decoded bytes against the reject limit.
 *
 * It reads URLDECODE_BLOCK_LOAD bytes from 'in', which for the AVX2 body
 * is a little more than the triplets cover. The caller makes sure that
 * many bytes exist.
 *
 * There are two bodies, selected at build time: AVX2 and plain C. They
 * must produce identical results.
 */

#define URLDECODE_BLOCK_TRIPLETS 10

#ifdef USE_AVX2

/* one 32 byte load holds ten triplets, plus two bytes that are ignored */
#define URLDECODE_BLOCK_LOAD 32

/* bit i set when byte i is a '%' in a run of ten triplets */
#define URLDECODE_PCT_MASK 0x09249249U
/* bit i set when byte i is a hex digit in a run of ten triplets */
#define URLDECODE_HEX_MASK 0x36db6db6U
/* bits 30 and 31 are not part of any triplet */
#define URLDECODE_CARE_MASK 0x3fffffffU

/* vpshufb moves bytes within each 128 bit lane only. The low lane holds
   triplets 0-4 at bytes 0-14 and the high lane holds triplets 5-9 at bytes
   16-29, so this control gathers the first byte of each triplet from both
   lanes into output positions 0-4 and 5-9, zeroing the rest; the two lanes
   then OR together into ten bytes. */
static const uint8_t urldecode_pack_ctrl[32] = {
  1, 4, 7, 10, 13, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80,
  0x80, 0x80,
  0x80, 0x80, 0x80, 0x80, 0x80, 0, 3, 6, 9, 12, 0x80, 0x80, 0x80, 0x80,
  0x80, 0x80
};

/* 'nib' holds the nibble value of every hex digit byte. Combine each pair
   into one byte and store the ten bytes to 'out'. */
static CURL_INLINE void urldecode_pack(__m256i nib, uint8_t *out)
{
  __m256i x;
  __m128i r;
  uint16_t tail;

  /* x[i] = nib[i] << 4 | nib[i + 1]: the first byte of every triplet now
     holds its decoded value. Bytes that are not hex digits hold garbage,
     the mask keeps their bits from leaking across the 16 bit shift. */
  x = _mm256_or_si256(
    _mm256_slli_epi16(_mm256_and_si256(nib, _mm256_set1_epi8(0x0f)), 4),
    _mm256_bsrli_epi128(nib, 1));
  x = _mm256_shuffle_epi8(
    x, _mm256_loadu_si256((const __m256i *)(const void *)urldecode_pack_ctrl));
  r = _mm_or_si128(_mm256_castsi256_si128(x),
                   _mm256_extracti128_si256(x, 1));
  _mm_storel_epi64((__m128i *)(void *)out, r);
  tail = (uint16_t)_mm_extract_epi16(r, 4);
  memcpy(out + 8, &tail, sizeof(tail));
}

static CURL_INLINE bool urldecode_block(const char *in, uint8_t *out)
{
  __m256i v, d, a, digit, letter;
  unsigned int m;

  v = _mm256_loadu_si256((const __m256i *)(const void *)in);

  /* every third byte starting at zero must be a '%' */
  m = (unsigned int)_mm256_movemask_epi8(
    _mm256_cmpeq_epi8(v, _mm256_set1_epi8('%')));
  if((m & URLDECODE_CARE_MASK) != URLDECODE_PCT_MASK)
    return FALSE;

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
    return FALSE;

  /* nibble value: d for digits, a + 10 for letters */
  urldecode_pack(_mm256_blendv_epi8(_mm256_add_epi8(a,
                                                    _mm256_set1_epi8(10)),
                                    d, digit), out);
  return TRUE;
}

#else /* plain C */

#define URLDECODE_BLOCK_LOAD (3 * URLDECODE_BLOCK_TRIPLETS)

static CURL_INLINE bool urldecode_block(const char *in, uint8_t *out)
{
  size_t i;

  for(i = 0; i < URLDECODE_BLOCK_TRIPLETS; i++, in += 3) {
    uint8_t h1 = hextable[(uint8_t)in[1]];
    uint8_t h2 = hextable[(uint8_t)in[2]];
    if((in[0] != '%') || ((h1 | h2) & 0xf0))
      return FALSE;
    out[i] = (uint8_t)((h1 << 4) | h2);
  }
  return TRUE;
}

#endif /* USE_AVX2 / C */

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
      memcpy(target + 1, hexpairs[in], 2);
      target += 3;
    }
  }
  if(nappend) {
    memcpy(target, f, nappend);
    target += nappend;
  }
  *target = '\0'; /* null-terminate */

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
      if((alloc >= URLDECODE_BLOCK_LOAD) &&
         urldecode_block(string, (uint8_t *)ns)) {
        if(reject_limit) {
          size_t i;
          for(i = 0; i < URLDECODE_BLOCK_TRIPLETS; i++) {
            if((uint8_t)ns[i] < reject_limit)
              goto error;
          }
        }
        ns += URLDECODE_BLOCK_TRIPLETS;
        string += 3 * URLDECODE_BLOCK_TRIPLETS;
        alloc -= 3 * URLDECODE_BLOCK_TRIPLETS;
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
