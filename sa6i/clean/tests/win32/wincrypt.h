// SPDX-License-Identifier: GPL-3.0-or-later
// Test-only WinCrypt declarations; no actual cryptography.
#ifndef FAKE_WINCRYPT_H
#define FAKE_WINCRYPT_H
#include <windows.h>
typedef uintptr_t HCRYPTPROV;
typedef uintptr_t HCRYPTHASH;
#define PROV_RSA_AES 24u
#define CRYPT_VERIFYCONTEXT 0xf0000000u
#define CALG_SHA_256 0x0000800cu
#define HP_HASHVAL 2u
BOOL CryptAcquireContextW(HCRYPTPROV *, const wchar_t *, const wchar_t *, DWORD, DWORD);
BOOL CryptCreateHash(HCRYPTPROV, DWORD, uintptr_t, DWORD, HCRYPTHASH *);
BOOL CryptHashData(HCRYPTHASH, const BYTE *, DWORD, DWORD);
BOOL CryptGetHashParam(HCRYPTHASH, DWORD, BYTE *, DWORD *, DWORD);
BOOL CryptDestroyHash(HCRYPTHASH);
BOOL CryptReleaseContext(HCRYPTPROV, DWORD);
#endif
