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
#include "unitcheck.h"

#include "escape.h"
#include "curlx/strparse.h"

/* the largest step any urldecode_run() body takes, in triplets */
#define T1688_MAX_TRIPLETS 64

/* Return a buffer of exactly 'len' bytes holding 'n' valid triplets that
   encode the bytes 'start', 'start' + 1, ..., followed by 'z' padding. Odd
   triplets use lower case hex digits, even ones upper case. The buffer is
   not null terminated, so a read past the end is caught by the address
   sanitizer or valgrind. */
static char *t1688_buf(size_t n, uint8_t start, size_t len)
{
  static const char upper[] = "0123456789ABCDEF";
  static const char lower[] = "0123456789abcdef";
  char *buf;
  size_t i;
  if(len < 3 * n)
    return NULL;
  buf = curlx_malloc(len);
  if(!buf)
    return NULL;
  for(i = 0; i < n; i++) {
    const char *digits = (i & 1) ? lower : upper;
    uint8_t value = (uint8_t)(start + i);
    buf[3 * i] = '%';
    buf[3 * i + 1] = digits[value >> 4];
    buf[3 * i + 2] = digits[value & 0x0f];
  }
  memset(buf + 3 * n, 'z', len - 3 * n);
  return buf;
}

/* Reference decoder: the documented behavior of Curl_urldecode() written
   one triplet at a time, with no run helper. */
static CURLcode t1688_reference(const char *in, size_t inlen,
                                char *out, size_t *outlen,
                                enum urlreject ctrl)
{
  size_t o = 0;
  uint8_t limit = (ctrl == REJECT_CTRL) ? 0x20 :
    (ctrl == REJECT_ZERO) ? 1 : 0;
  while(inlen) {
    uint8_t c = (uint8_t)*in;
    if((c == '%') && (inlen > 2) && ISXDIGIT(in[1]) && ISXDIGIT(in[2])) {
      c = (uint8_t)((curlx_hexval(in[1]) << 4) | curlx_hexval(in[2]));
      in += 3;
      inlen -= 3;
    }
    else {
      in++;
      inlen--;
    }
    if(c < limit)
      return CURLE_URL_MALFORMAT;
    out[o++] = (char)c;
  }
  *outlen = o;
  return CURLE_OK;
}

/* Decode 'in' with Curl_urldecode() and compare with the reference */
static void t1688_check(const char *in, size_t inlen, enum urlreject ctrl,
                        const char *what)
{
  char *ref = curlx_malloc(inlen + 1);
  char *got = NULL;
  size_t reflen = 0;
  size_t gotlen = 0;
  CURLcode refres;
  CURLcode gotres;

  abort_unless(ref, "out of memory");
  refres = t1688_reference(in, inlen, ref, &reflen, ctrl);
  gotres = Curl_urldecode(in, inlen, &got, &gotlen, ctrl);
  if(refres != gotres) {
    curl_mfprintf(stderr, "%s: expected result %d, got %d\n", what,
                  (int)refres, (int)gotres);
    unitfail++;
  }
  else if(!refres) {
    if(reflen != gotlen) {
      curl_mfprintf(stderr, "%s: expected length %zu, got %zu\n", what,
                    reflen, gotlen);
      unitfail++;
    }
    else if(memcmp(ref, got, reflen)) {
      curl_mfprintf(stderr, "%s: decoded data differs\n", what);
      unitfail++;
    }
  }
  curlx_free(got);
unit_test_abort:
  curlx_free(ref);
}

static CURLcode test_unit1688(const char *arg)
{
  UNITTEST_BEGIN_SIMPLE

  uint8_t out[T1688_MAX_TRIPLETS];
  uint8_t expect[T1688_MAX_TRIPLETS];
  bool rejected = FALSE;
  size_t step;
  size_t need;
  size_t used;
  size_t i;
  int start;
  char *buf;

  /* find the step size of the body this build uses */
  buf = t1688_buf(T1688_MAX_TRIPLETS, 0, 3 * T1688_MAX_TRIPLETS);
  abort_unless(buf, "out of memory");
  used = urldecode_run_unit(buf, 3 * T1688_MAX_TRIPLETS, out, 0,
                            &rejected);
  curlx_free(buf);
  fail_unless(used && !(used % 3), "a full run must be consumed");
  fail_unless(!rejected, "nothing to reject with REJECT_NADA");
  step = used / 3;
  abort_unless(step && (step <= T1688_MAX_TRIPLETS), "unusable step");

  /* find the shortest input for which a step is consumed: the vector
     bodies load a few more bytes than they consume */
  need = 3 * step;
  for(;;) {
    buf = t1688_buf(step, 0x41, need);
    abort_unless(buf, "out of memory");
    rejected = FALSE;
    used = urldecode_run_unit(buf, need, out, 0, &rejected);
    curlx_free(buf);
    if(used)
      break;
    need++;
    abort_unless(need <= 3 * step + 64, "no input length consumes a step");
  }
  fail_unless(used == 3 * step, "exactly one step must be consumed");
  curl_mprintf("urldecode_run() step is %zu triplets, needs %zu bytes\n",
               step, need);

  /* 1. every byte value, upper and lower case, decoded exactly */
  for(start = 0; start < 256; start += (int)step) {
    buf = t1688_buf(step, (uint8_t)start, need);
    abort_unless(buf, "out of memory");
    for(i = 0; i < step; i++)
      expect[i] = (uint8_t)(start + (int)i);
    memset(out, 0xaa, sizeof(out));
    rejected = FALSE;
    used = urldecode_run_unit(buf, need, out, 0, &rejected);
    fail_unless(used == 3 * step, "full step not consumed");
    fail_unless(!rejected, "unexpected rejection");
    fail_unless(!memcmp(out, expect, step), "decoded bytes differ");
    t1688_check(buf, need, REJECT_NADA, "all values");
    curlx_free(buf);
  }

  /* 2. one byte short is left to the scalar code */
  buf = t1688_buf(step, 0x41, need);
  abort_unless(buf, "out of memory");
  rejected = FALSE;
  used = urldecode_run_unit(buf, need - 1, out, 0, &rejected);
  fail_unless(!used, "short input must not be consumed");
  fail_unless(!rejected, "short input must not be rejected");
  t1688_check(buf, need - 1, REJECT_NADA, "short input");
  t1688_check(buf, 3 * step - 1, REJECT_NADA, "truncated run");
  curlx_free(buf);

  /* 3. a bad byte in any lane makes the whole step fall back */
  for(i = 0; i < step; i++) {
    static const char bad[] = { 'x', 'G', 'g', '/', ':', '@', '`',
                                '\x80', '\xff' };
    size_t b;
    for(b = 0; b < sizeof(bad); b++) {
      size_t pos;
      for(pos = 0; pos < 3; pos++) {
        buf = t1688_buf(step, 0x41, need);
        abort_unless(buf, "out of memory");
        buf[3 * i + pos] = bad[b];
        rejected = FALSE;
        used = urldecode_run_unit(buf, need, out, 0, &rejected);
        fail_unless(!used, "invalid run must not be consumed");
        fail_unless(!rejected, "invalid run must not be rejected");
        t1688_check(buf, need, REJECT_NADA, "invalid run");
        t1688_check(buf, need, REJECT_CTRL, "invalid run ctrl");
        curlx_free(buf);
      }
    }
  }

  /* 4. reject semantics per lane */
  for(i = 0; i < step; i++) {
    buf = t1688_buf(step, 0x41, need);
    abort_unless(buf, "out of memory");

    /* %00 fails REJECT_ZERO and REJECT_CTRL, passes REJECT_NADA */
    buf[3 * i + 1] = '0';
    buf[3 * i + 2] = '0';
    rejected = FALSE;
    used = urldecode_run_unit(buf, need, out, 1, &rejected);
    fail_unless(!used && rejected, "%00 must be rejected with limit 1");
    rejected = FALSE;
    used = urldecode_run_unit(buf, need, out, 0x20, &rejected);
    fail_unless(!used && rejected, "%00 must be rejected with limit 0x20");
    rejected = FALSE;
    used = urldecode_run_unit(buf, need, out, 0, &rejected);
    fail_unless((used == 3 * step) && !rejected, "%00 must pass limit 0");
    fail_unless(!out[i], "%00 must decode to 0");
    t1688_check(buf, need, REJECT_ZERO, "%00 zero");
    t1688_check(buf, need, REJECT_CTRL, "%00 ctrl");
    t1688_check(buf, need, REJECT_NADA, "%00 nada");

    /* %1F fails REJECT_CTRL only */
    buf[3 * i + 1] = '1';
    buf[3 * i + 2] = 'f';
    rejected = FALSE;
    used = urldecode_run_unit(buf, need, out, 0x20, &rejected);
    fail_unless(!used && rejected, "%1f must be rejected with limit 0x20");
    rejected = FALSE;
    used = urldecode_run_unit(buf, need, out, 1, &rejected);
    fail_unless((used == 3 * step) && !rejected, "%1f must pass limit 1");
    fail_unless(out[i] == 0x1f, "%1f must decode to 0x1f");
    t1688_check(buf, need, REJECT_ZERO, "%1f zero");
    t1688_check(buf, need, REJECT_CTRL, "%1f ctrl");

    /* %20 passes everything */
    buf[3 * i + 1] = '2';
    buf[3 * i + 2] = '0';
    rejected = FALSE;
    used = urldecode_run_unit(buf, need, out, 0x20, &rejected);
    fail_unless((used == 3 * step) && !rejected, "%20 must pass");
    fail_unless(out[i] == 0x20, "%20 must decode to 0x20");
    t1688_check(buf, need, REJECT_CTRL, "%20 ctrl");

    /* %FF passes everything */
    buf[3 * i + 1] = 'F';
    buf[3 * i + 2] = 'F';
    rejected = FALSE;
    used = urldecode_run_unit(buf, need, out, 0x20, &rejected);
    fail_unless((used == 3 * step) && !rejected, "%FF must pass");
    fail_unless(out[i] == 0xff, "%FF must decode to 0xff");
    t1688_check(buf, need, REJECT_CTRL, "%FF ctrl");
    curlx_free(buf);
  }

  /* 5. runs of different lengths next to literal data, end to end */
  for(i = 0; i < 3 * step + 2; i++) {
    static const char lit[] = "/path?q=a+b&x=%";
    size_t litlen = sizeof(lit) - 1;
    size_t ntrip = 2 * step + 1;
    size_t len = litlen + 3 * ntrip + i + litlen;
    char *in = t1688_buf(0, 0, len);
    char *trip = t1688_buf(ntrip, 0x20, 3 * ntrip);
    abort_unless(trip && in, "out of memory");
    memcpy(in, lit, litlen);
    memcpy(in + litlen, trip, 3 * ntrip);
    memcpy(in + litlen + 3 * ntrip + i, lit, litlen);
    t1688_check(in, len, REJECT_NADA, "mixed nada");
    t1688_check(in, len, REJECT_CTRL, "mixed ctrl");
    t1688_check(in, len, REJECT_ZERO, "mixed zero");
    /* a trailing truncated triplet */
    t1688_check(in, len - 1, REJECT_CTRL, "mixed truncated");
    /* a run that ends exactly at the end of the input */
    t1688_check(in + litlen, 3 * step, REJECT_CTRL, "exact step");
    t1688_check(in + litlen, 3 * step + 3, REJECT_CTRL, "step plus one");
    t1688_check(in + litlen, 3 * ntrip, REJECT_CTRL, "two steps plus one");
    curlx_free(trip);
    curlx_free(in);
  }

  /* 6. literal data interleaved with single triplets, never a run */
  {
    static const char single[] =
      "a%41b%42c%43d%44e%45f%46g%47h%48i%49j%4Ak%4bl%4cm%4dn%4eo%4fp%50"
      "q%51r%52s%53t%54u%55v%56w%57x%58y%59z%5a%%%25%2%%G1%";
    t1688_check(single, sizeof(single) - 1, REJECT_NADA, "singles nada");
    t1688_check(single, sizeof(single) - 1, REJECT_CTRL, "singles ctrl");
  }

  UNITTEST_END_SIMPLE
}
