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

static CURLcode t1396_setup(void)
{
  CURLcode result = CURLE_OK;
  global_init(CURL_GLOBAL_ALL);
  return result;
}

static void t1396_stop(CURL *easy)
{
  if(easy)
    curl_easy_cleanup(easy);
  curl_global_cleanup();
}

static CURLcode test_lib1396(const char *arg)
{
  CURL *easy;

  UNITTEST_BEGIN(t1396_setup())

  struct test {
    const char *in;
    int inlen;
    const char *out;
    int outlen;
  };

  /* unescape, this => that */
  static const struct test list1[] = {
    { "%61", 3, "a", 1 },
    { "%61a", 4, "aa", 2 },
    { "%61b", 4, "ab", 2 },
    { "%6 1", 4, "%6 1", 4 },
    { "%61", 1, "%", 1 },
    { "%61", 2, "%6", 2 },
    { "%6%a", 4, "%6%a", 4 },
    { "%6a", 0, "j", 1 },
    { "%FF", 0, "\xff", 1 },
    { "%FF%00%ff", 9, "\xff\x00\xff", 3 },
    { "%-2", 0, "%-2", 3 },
    { "%FG", 0, "%FG", 3 },
    /* runs of ten or more triplets are decoded a block at a time */
    { "%41%42%43%44%45%46%47%48%49%4a", 30, "ABCDEFGHIJ", 10 },
    { "%41%42%43%44%45%46%47%48%49%4a", 29, "ABCDEFGHI%4", 11 },
    { "%41%42%43%44%45%46%47%48%49%4a%4b", 0, "ABCDEFGHIJK", 11 },
    { "%41%42%43%44%45%46%47%48%49%4a%41%42%43%44%45%46%47%48%49%4a", 0,
      "ABCDEFGHIJABCDEFGHIJ", 20 },
    { "%41%42%43%44%45%46%47%48%49%4ax%41%42%43%44%45%46%47%48%49%4a", 0,
      "ABCDEFGHIJxABCDEFGHIJ", 21 },
    { "%00%01%1f%20%7f%80%fe%FF%00%ff", 0,
      "\x00\x01\x1f\x20\x7f\x80\xfe\xff\x00\xff", 10 },
    /* a byte that is not a hex digit anywhere in the run */
    { "x41%42%43%44%45%46%47%48%49%4a", 0, "x41BCDEFGHIJ", 12 },
    { "%/1%42%43%44%45%46%47%48%49%4a", 0, "%/1BCDEFGHIJ", 12 },
    { "%41%4:%43%44%45%46%47%48%49%4a", 0, "A%4:CDEFGHIJ", 12 },
    { "%41%42%43%44%@5%46%47%48%49%4a", 0, "ABCD%@5FGHIJ", 12 },
    { "%41%42%43%44%45%4G%47%48%49%4a", 0, "ABCDE%4GGHIJ", 12 },
    { "%41%42%43%44%45%46%47%48%`9%4a", 0, "ABCDEFGH%`9J", 12 },
    { "%41%42%43%44%45%46%47%48%49%4g", 0, "ABCDEFGHI%4g", 12 },
    { "%41%42%43%44%45%46%47%48%49%4\xff", 0, "ABCDEFGHI%4\xff", 12 },
    { NULL, 0, NULL, 0 } /* end of list marker */
  };
  /* escape, this => that */
  static const struct test list2[] = {
    { "a", 1, "a", 1 },
    { "-", 1, "-", 1 },
    { ".", 1, ".", 1 },
    { "_", 1, "_", 1 },
    { "~", 1, "~", 1 },
    { "/", 1, "%2F", 3 },
    { "a=b", 3, "a%3Db", 5 },
    { "a=b", 0, "a%3Db", 5 },
    { "a=b", 1, "a", 1 },
    { "a=b", 2, "a%3D", 4 },
    { "1/./0", 5, "1%2F.%2F0", 9 },
    { "-._~!#%&", 0, "-._~%21%23%25%26", 16 },
    { "a", 2, "a%00", 4 },
    { "a\xff\x01g", 4, "a%FF%01g", 8 },
    { NULL, 0, NULL, 0 } /* end of list marker */
  };
  int i;

  easy = curl_easy_init();
  abort_unless(easy, "returned NULL!");
  for(i = 0; list1[i].in; i++) {
    int outlen;
    char *out = curl_easy_unescape(easy, list1[i].in, list1[i].inlen, &outlen);

    abort_unless(out, "returned NULL!");
    fail_unless(outlen == list1[i].outlen, "wrong output length returned");
    fail_unless(!memcmp(out, list1[i].out, list1[i].outlen),
                "bad output data returned");

    curl_mprintf("curl_easy_unescape test %d DONE\n", i);

    curl_free(out);
  }

  /* every byte value in one run of triplets, odd triplets in lower case
     hex and even ones in upper case */
  {
    static const char upper[] = "0123456789ABCDEF";
    static const char lower[] = "0123456789abcdef";
    char in[3 * 256];
    int outlen;
    char *out;
    for(i = 0; i < 256; i++) {
      const char *digits = (i & 1) ? lower : upper;
      in[3 * i] = '%';
      in[3 * i + 1] = digits[i >> 4];
      in[3 * i + 2] = digits[i & 0x0f];
    }
    out = curl_easy_unescape(easy, in, (int)sizeof(in), &outlen);
    abort_unless(out, "returned NULL!");
    fail_unless(outlen == 256, "wrong output length returned");
    for(i = 0; i < outlen; i++)
      fail_unless((unsigned char)out[i] == i, "bad output data returned");
    curl_mprintf("curl_easy_unescape all byte values DONE\n");
    curl_free(out);
  }

  for(i = 0; list2[i].in; i++) {
    int outlen;
    char *out = curl_easy_escape(easy, list2[i].in, list2[i].inlen);
    abort_unless(out, "returned NULL!");

    outlen = (int)strlen(out);
    fail_unless(outlen == list2[i].outlen, "wrong output length returned");
    fail_unless(!memcmp(out, list2[i].out, list2[i].outlen),
                "bad output data returned");

    curl_mprintf("curl_easy_escape test %d DONE (%s)\n", i, out);

    curl_free(out);
  }

  {
    unsigned char binary[256];
    char expected[sizeof(binary) * 3 + 1];
    const char digits[] = "0123456789ABCDEF";
    size_t encoded_length = 0;
    unsigned int byte;
    char *encoded;
    char *decoded;
    int decoded_length;

    for(byte = 0; byte < sizeof(binary); byte++) {
      binary[byte] = (unsigned char)byte;
      if((byte >= 'a' && byte <= 'z') || (byte >= 'A' && byte <= 'Z') ||
         (byte >= '0' && byte <= '9') || byte == '-' || byte == '.' ||
         byte == '_' || byte == '~')
        expected[encoded_length++] = (char)byte;
      else {
        expected[encoded_length++] = '%';
        expected[encoded_length++] = digits[byte >> 4];
        expected[encoded_length++] = digits[byte & 15];
      }
    }
    expected[encoded_length] = 0;
    encoded = curl_easy_escape(easy, (const char *)binary, sizeof(binary));
    abort_unless(encoded, "binary escape failed");
    fail_unless(!strcmp(encoded, expected), "wrong binary escape output");
    decoded = curl_easy_unescape(easy, encoded, 0, &decoded_length);
    curl_free(encoded);
    abort_unless(decoded, "binary unescape failed");
    fail_unless(decoded_length == sizeof(binary), "wrong binary output size");
    if(decoded_length == sizeof(binary)) {
      fail_unless(!memcmp(decoded, binary, sizeof(binary)),
                  "wrong binary data");
      fail_unless(!decoded[decoded_length], "binary output not terminated");
    }
    curl_free(decoded);
  }

  UNITTEST_END(t1396_stop(easy))
}
