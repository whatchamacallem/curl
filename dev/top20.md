# Top 20 leaf functions by CPU (self cost, Ir events)

Source: `dev/callgrind-out/callgrind.out.urlparser.200.1789436338`
(`loops=200`, RelWithDebInfo `-O2 -g`, pinned callgrind run), 1,977,196,759
total instructions retired. "Top called by" is the incoming call-edge
breakdown by inclusive-cost share (top 3 callers, `%` of this function's
total calls attributable to that caller). Addresses like `0x0000...` are
unresolved/inlined call sites inside libc (glibc's IFUNC resolver stubs and
PLT trampolines for the AVX2 string routines) — callgrind cannot attach a
symbol name to them.

| # | Ir (self) | % | Function | Top called by |
|---|-----------|---|----------|----------------|
| 1 | 747,778,000 | 37.82% | `lib/urlapi.c:parseurl_and_replace` | `curl_url_set` (100%) |
| 2 | 156,483,600 | 7.91% | `lib/urlapi.c:Curl_is_absolute_url` | `parseurl_and_replace` (56%); `curl_url_set` (44%) |
| 3 | 124,515,734 | 6.30% | `__memchr_avx2` (glibc) | inlined/PLT call site (100%) |
| 4 | 123,057,451 | 6.22% | `free` (glibc malloc) | `free_urlhandle` (82%); `parse_authority` (16%); `curlx_dyn_free` (1%) |
| 5 | 110,494,000 | 5.59% | `lib/urlapi.c:parse_authority` | `parseurl_and_replace` (100%) |
| 6 | 76,728,000 | 3.88% | `lib/urlapi.c:hostname_check` | `parse_authority` (100%) |
| 7 | 76,276,000 | 3.86% | `lib/curlx/dynbuf.c:dyn_nappend` | `curlx_dyn_addn` (100%) |
| 8 | 73,738,107 | 3.73% | `malloc` (glibc) | `curlx_memdup0` (36%); `realloc` (34%); inlined call site (29%) |
| 9 | 60,431,677 | 3.06% | `__strlen_avx2` (glibc) | inlined/PLT call site (81%); inlined/PLT call site (19%) |
| 10 | 50,547,800 | 2.56% | `lib/urlapi.c:curl_url_set` | test harness / inlined call site (100%) |
| 11 | 43,096,293 | 2.18% | `lib/mprintf.c:formatf` | `curlx_dyn_vprintf` (64%); `curl_mvaprintf` (29%); `curl_mvsnprintf` (7%) |
| 12 | 42,896,536 | 2.17% | `__memcpy_avx_unaligned_erms` (glibc) | inlined/PLT call site (99%); inlined/PLT call site (1%) |
| 13 | 25,250,400 | 1.28% | `lib/curlx/strdup.c:curlx_memdup0` | `parseurl_and_replace` (96%); `Curl_parse_login_details` (4%) |
| 14 | 23,426,229 | 1.18% | `lib/urlapi.c:free_urlhandle` | `parseurl_and_replace` (100%); `curl_url_cleanup` (0%) |
| 15 | 19,125,600 | 0.97% | `lib/protocol.c:five_letter_scheme` | `Curl_getn_scheme` (97%); `Curl_get_scheme` (3%) |
| 16 | 18,067,400 | 0.91% | `__memcpy_chk_avx_unaligned_erms` (glibc) | inlined/PLT call site (100%) |
| 17 | 16,428,000 | 0.83% | `strdup` (glibc) | `parseurl_and_replace` (97%); `ipv6_parse` (3%) |
| 18 | 14,960,000 | 0.76% | `lib/curlx/inet_pton.c:curlx_inet_pton` | `ipv6_parse` (100%) |
| 19 | 13,444,282 | 0.68% | `lib/curlx/strparse.c:str_num_base` | `curlx_str_number` (93%); `curlx_str_octal` (7%) |
| 20 | 12,430,000 | 0.63% | `lib/curlx/inet_ntop.c:curlx_inet_ntop` | `ipv6_parse` (100%) |

## Notes

- Ranks 1-2, 5-6, 13-14, 17 are all inside the `curl_url_set(CURLUPART_URL,
  ...)` → `parseurl_and_replace` call tree — consistent with CLAUDE.md's
  documented finding that `parseurl_and_replace` alone (with inlined helpers
  like `badoctets()`) dominates the profile under `-O2`.
- Ranks 3, 8, 9, 12, 16 are glibc allocator/string primitives
  (`malloc`/`free`/`memchr`/`strlen`/`memcpy`), called from many sites —
  their "inlined/PLT call site" callers are glibc's own IFUNC dispatch
  stubs, not curl code, so no single curl call site owns them.
- Rank 4 (`free`, 6.22%) is called overwhelmingly (82%) from
  `free_urlhandle`, confirming CLAUDE.md's note that teardown/rebuild of the
  handle on every `curl_url_set(CURLUPART_URL, ...)` call is a real,
  independent cost center from parsing itself.
- Rank 7 (`dyn_nappend`, 3.86%) and rank 11 (`formatf`, 2.18%) trace back to
  dynbuf/mprintf usage inside URL reconstruction, not raw parsing.
