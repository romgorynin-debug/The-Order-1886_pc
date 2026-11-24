// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
// FidelityFX SDK 1.1.4 assumes Microsoft CRT conveniences in its Windows host.
// Include the CRT headers before defining any missing compatibility macros.
// Only force-included for the FSR3 host target on MinGW.
#include <cstdlib>
#include <cwchar>
#include <iterator>

#ifndef _countof
#define _countof(array) (::std::size(array))
#endif

// The SDK uses this only to format a bounded diagnostic wide-character buffer.
// The standard C++ function has the same buffer/size/format argument order.
#ifndef swprintf_s
#define swprintf_s(...) (::std::swprintf(__VA_ARGS__))
#endif
