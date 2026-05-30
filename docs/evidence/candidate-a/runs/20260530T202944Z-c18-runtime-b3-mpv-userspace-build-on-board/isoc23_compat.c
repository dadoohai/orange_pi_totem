/* Compat shim: provide glibc>=2.38 __isoc23_* conversion symbols as aliases to the
 * classic C functions, so a GCC-13/glibc-2.39-built libstdc++.a links and runs on the
 * board's glibc 2.36. Semantics differ only for C23 base-prefix parsing (0b...), which
 * libstdc++'s internal use does not rely on. */
#define _GNU_SOURCE
#include <stdlib.h>
#include <stdio.h>
#include <stdarg.h>
#include <wchar.h>
#include <inttypes.h>

long               __isoc23_strtol  (const char*s,char**e,int b){return strtol(s,e,b);}
unsigned long      __isoc23_strtoul (const char*s,char**e,int b){return strtoul(s,e,b);}
long long          __isoc23_strtoll (const char*s,char**e,int b){return strtoll(s,e,b);}
unsigned long long __isoc23_strtoull(const char*s,char**e,int b){return strtoull(s,e,b);}
intmax_t           __isoc23_strtoimax(const char*s,char**e,int b){return strtoimax(s,e,b);}
uintmax_t          __isoc23_strtoumax(const char*s,char**e,int b){return strtoumax(s,e,b);}
long               __isoc23_wcstol  (const wchar_t*s,wchar_t**e,int b){return wcstol(s,e,b);}
unsigned long      __isoc23_wcstoul (const wchar_t*s,wchar_t**e,int b){return wcstoul(s,e,b);}
long long          __isoc23_wcstoll (const wchar_t*s,wchar_t**e,int b){return wcstoll(s,e,b);}
unsigned long long __isoc23_wcstoull(const wchar_t*s,wchar_t**e,int b){return wcstoull(s,e,b);}

int __isoc23_vsscanf(const char*s,const char*f,va_list a){return vsscanf(s,f,a);}
int __isoc23_sscanf (const char*s,const char*f,...){va_list a;va_start(a,f);int r=vsscanf(s,f,a);va_end(a);return r;}
int __isoc23_vfscanf(FILE*st,const char*f,va_list a){return vfscanf(st,f,a);}
int __isoc23_fscanf (FILE*st,const char*f,...){va_list a;va_start(a,f);int r=vfscanf(st,f,a);va_end(a);return r;}
int __isoc23_vscanf (const char*f,va_list a){return vscanf(f,a);}
int __isoc23_scanf  (const char*f,...){va_list a;va_start(a,f);int r=vscanf(f,a);va_end(a);return r;}
