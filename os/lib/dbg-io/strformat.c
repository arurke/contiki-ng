/*
 * Copyright (c) 2009, Simon Berg
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 * 3. Neither the name of the copyright holder nor the names of its
 *    contributors may be used to endorse or promote products derived
 *    from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * ``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
 * FOR A PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE
 * COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
 * INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
 * (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 * SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
 * STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
 * OF THE POSSIBILITY OF SUCH DAMAGE.
 *---------------------------------------------------------------------------
 * floats print implementation ported from  https://github.com/mpaland/printf.git
 */
/*---------------------------------------------------------------------------*/
#include "contiki.h"
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#include <string.h>
#include "sys/cc.h"

#include "strformat.h"
/*---------------------------------------------------------------------------*/
#define HAVE_DOUBLE_EXP 1
#define HAVE_DOUBLE_HEX 2

#ifndef PRINTF_CONF_HAVE_DOUBLE
#define HAVE_DOUBLE     (HAVE_DOUBLE_EXP | HAVE_DOUBLE_HEX )
//#define HAVE_DOUBLE     (HAVE_DOUBLE_HEX )
#else
#define HAVE_DOUBLE     PRINTF_CONF_HAVE_DOUBLE
#endif
#ifndef PRINTF_CONF_HAVE_LONGLONG
#define HAVE_LONGLONG   1
#else
#define HAVE_LONGLONG   PRINTF_CONF_HAVE_LONGLONG
#endif

/*  HAVE_NETADDR provides pointer format specifier %p with more info:
 *      %pL - dumps pointer as linkaddr_t*
 *      %pI - dumps pointer as uip_ipaddr_t*
 * */
#ifndef PRINTF_CONF_HAVE_NETADDR
#define HAVE_NETADDR    1
#else
#define HAVE_NETADDR    PRINTF_CONF_HAVE_NETADDR
#endif


#if HAVE_NETADDR
#include "net/linkaddr.h"
#include "net/ipv6/uiplib.h"
#endif

#ifndef LARGEST_SIGNED
#if HAVE_LONGLONG
#define LARGEST_SIGNED long long int
#else
#define LARGEST_SIGNED long int
#endif /* HAVE_LONGLONG */
#endif /* LARGEST_SIGNED */

#ifndef LARGEST_UNSIGNED
#if HAVE_LONGLONG
#define LARGEST_UNSIGNED unsigned long long int
#else
#define LARGEST_UNSIGNED unsigned long int
#endif /* HAVE_LONGLONG */
#endif /* LARGEST_UNSIGNED */

#ifndef POINTER_INT
#define POINTER_INT uintptr_t
#endif
/*---------------------------------------------------------------------------*/
typedef uint32_t FormatFlags;
/*---------------------------------------------------------------------------*/
#define MAKE_MASK(shift, size) (((1 << size) - 1) << (shift))
/*---------------------------------------------------------------------------*/
#define JUSTIFY_SHIFT   0
#define JUSTIFY_SIZE    1
#define JUSTIFY_RIGHT   0x0000
#define JUSTIFY_LEFT    0x0001
#define JUSTIFY_MASK    MAKE_MASK(JUSTIFY_SHIFT, JUSTIFY_SIZE)
/*---------------------------------------------------------------------------*/
/* How a positive number is prefixed */
#define POSITIVE_SHIFT  (JUSTIFY_SHIFT + JUSTIFY_SIZE)
#define POSITIVE_NONE   (0x0000 << POSITIVE_SHIFT)
#define POSITIVE_SPACE  (0x0001 << POSITIVE_SHIFT)
#define POSITIVE_PLUS   (0x0003 << POSITIVE_SHIFT)
#define POSITIVE_MASK   MAKE_MASK(POSITIVE_SHIFT, POSITIVE_SIZE)

#define POSITIVE_SIZE   2
/*---------------------------------------------------------------------------*/
#define ALTERNATE_FORM_SHIFT (POSITIVE_SHIFT + POSITIVE_SIZE)
#define ALTERNATE_FORM_SIZE  1
#define ALTERNATE_FORM       (0x0001 << ALTERNATE_FORM_SHIFT)
/*---------------------------------------------------------------------------*/
#define PAD_SHIFT (ALTERNATE_FORM_SHIFT + ALTERNATE_FORM_SIZE)
#define PAD_SIZE  1
#define PAD_SPACE (0x0000 << PAD_SHIFT)
#define PAD_ZERO  (0x0001 << PAD_SHIFT)
/*---------------------------------------------------------------------------*/
#define SIZE_SHIFT    (PAD_SHIFT + PAD_SIZE)
#define SIZE_SIZE     3
#define SIZE_CHAR     (0x0001 << SIZE_SHIFT)
#define SIZE_SHORT    (0x0002 << SIZE_SHIFT)
#define SIZE_INT      (0x0000 << SIZE_SHIFT)
#define SIZE_LONG     (0x0003 << SIZE_SHIFT)
#define SIZE_LONGLONG (0x0004 << SIZE_SHIFT)
#define SIZE_MASK     MAKE_MASK(SIZE_SHIFT, SIZE_SIZE)
/*---------------------------------------------------------------------------*/
#define CONV_SHIFT    (SIZE_SHIFT + SIZE_SIZE)
#define CONV_SIZE     3
#define CONV_INTEGER  (0x0001 << CONV_SHIFT)
#define CONV_FLOAT    (0x0002 << CONV_SHIFT)
#define CONV_POINTER  (0x0003 << CONV_SHIFT)
#define CONV_STRING   (0x0004 << CONV_SHIFT)
#define CONV_CHAR     (0x0005 << CONV_SHIFT)
#define CONV_PERCENT  (0x0006 << CONV_SHIFT)
#define CONV_WRITTEN  (0x0007 << CONV_SHIFT)
#define CONV_MASK     MAKE_MASK(CONV_SHIFT, CONV_SIZE)
/*---------------------------------------------------------------------------*/
#define RADIX_SHIFT   (CONV_SHIFT + CONV_SIZE)
#define RADIX_SIZE    2
#define RADIX_DECIMAL (0x0001 << RADIX_SHIFT)
#define RADIX_OCTAL   (0x0002 << RADIX_SHIFT)
#define RADIX_HEX     (0x0003 << RADIX_SHIFT)
#define RADIX_MASK    MAKE_MASK(RADIX_SHIFT, RADIX_SIZE)
/*---------------------------------------------------------------------------*/
#define SIGNED_SHIFT  (RADIX_SHIFT + RADIX_SIZE)
#define SIGNED_SIZE   1
#define SIGNED_NO     (0x0000 << SIGNED_SHIFT)
#define SIGNED_YES    (0x0001 << SIGNED_SHIFT)
#define SIGNED_MASK   MAKE_MASK(SIGNED_SHIFT, SIGNED_SIZE)
/*---------------------------------------------------------------------------*/
#define CAPS_SHIFT  (SIGNED_SHIFT + SIGNED_SIZE)
#define CAPS_SIZE 1
#define CAPS_NO     (0x0000 << CAPS_SHIFT)
#define CAPS_YES    (0x0001 << CAPS_SHIFT)
#define CAPS_MASK   MAKE_MASK(CAPS_SHIFT, CAPS_SIZE)
/*---------------------------------------------------------------------------*/
#define FLOAT_SHIFT     (CAPS_SHIFT + CAPS_SIZE)
#define FLOAT_SIZE      2
#define FLOAT_NORMAL    (((uint32_t)0x0000) << FLOAT_SHIFT)
#define FLOAT_EXPONENT  (((uint32_t)0x0001) << FLOAT_SHIFT)
#define FLOAT_DEPENDANT (((uint32_t)0x0002) << FLOAT_SHIFT)
#define FLOAT_HEX       (((uint32_t)0x0003) << FLOAT_SHIFT)
#define FLOAT_MASK      MAKE_MASK(FLOAT_SHIFT, FLOAT_SIZE)
/*---------------------------------------------------------------------------*/
#define CHECKCB(res) { if((res) != STRFORMAT_OK) { return -1; } }
/*---------------------------------------------------------------------------*/
#define MAXCHARS_HEX ((sizeof(LARGEST_UNSIGNED) * 8) / 4)

/* Largest number of characters needed for converting an unsigned integer. */
#define MAXCHARS ((sizeof(LARGEST_UNSIGNED) * 8 + 2) / 3)
/*---------------------------------------------------------------------------*/
static FormatFlags
parse_flags(const char **posp)
{
  FormatFlags flags = 0;
  const char *pos = *posp;

  while(1) {
    switch(*pos) {
    case '-':
      flags |= JUSTIFY_LEFT;
      break;
    case '+':
      flags |= POSITIVE_PLUS;
      break;
    case ' ':
      flags |= POSITIVE_SPACE;
      break;
    case '#':
      flags |= ALTERNATE_FORM;
      break;
    case '0':
      flags |= PAD_ZERO;
      break;
    default:
      *posp = pos;
      return flags;
    }

    pos++;
  }
}
/*---------------------------------------------------------------------------*/
static unsigned int
parse_uint(const char **posp)
{
  unsigned v = 0;
  const char *pos = *posp;
  char ch;

  while((ch = *pos) >= '0' && ch <= '9') {
    v = v * 10 + (ch - '0');
    pos++;
  }

  *posp = pos;

  return v;
}
/*---------------------------------------------------------------------------*/
static unsigned int
output_uint_decimal(char **posp, LARGEST_UNSIGNED v)
{
  unsigned int len;
  char *pos = *posp;

  do {
    *--pos = (v % 10) + '0';
    v /= 10;
  } while (v > 0);

  len = *posp - pos;
  *posp = pos;

  return len;
}
/*---------------------------------------------------------------------------*/
static unsigned int
output_uint_hex(char **posp, LARGEST_UNSIGNED v, unsigned int flags)
{
  unsigned int len;
  const char *hex = (flags & CAPS_YES) ? "0123456789ABCDEF" : "0123456789abcdef";
  char *pos = *posp;

  do {
    *--pos = hex[(v % 16)];
    v /= 16;
  } while(v > 0);

  len = *posp - pos;
  *posp = pos;

  return len;
}
/*---------------------------------------------------------------------------*/
static unsigned int
output_uint_octal(char **posp, LARGEST_UNSIGNED v)
{
  unsigned int len;
  char *pos = *posp;

  do {
    *--pos = (v % 8) + '0';
    v /= 8;
  } while(v > 0);

  len = *posp - pos;
  *posp = pos;

  return len;
}

static
unsigned output_radix_num(char **conv_pos, FormatFlags flags, LARGEST_UNSIGNED uvalue ){
    switch(flags & (RADIX_MASK)) {
    case RADIX_DECIMAL: return output_uint_decimal(conv_pos, uvalue);
    case RADIX_OCTAL:   return output_uint_octal(conv_pos, uvalue);
    case RADIX_HEX:     return output_uint_hex(conv_pos, uvalue, flags);
    }
    return 0;
}
/*---------------------------------------------------------------------------*/
static strformat_result
fill_space(const strformat_context_t *ctxt, unsigned int len)
{
  strformat_result res;
  static const char buffer[16] = "                ";

  while(len > 16) {
    res = ctxt->write_str(ctxt->user_data, buffer, 16);
    if(res != STRFORMAT_OK) {
      return res;
    }
    len -= 16;
  }

  if(len == 0) {
    return STRFORMAT_OK;
  }

  return ctxt->write_str(ctxt->user_data, buffer, len);
}
/*---------------------------------------------------------------------------*/
static strformat_result
fill_zero(const strformat_context_t *ctxt, unsigned int len)
{
  strformat_result res;
  static const char buffer[16] = "0000000000000000";

  while(len > 16) {
    res = ctxt->write_str(ctxt->user_data, buffer, 16);
    if(res != STRFORMAT_OK) {
      return res;
    }
    len -= 16;
  }

  if(len == 0) {
    return STRFORMAT_OK;
  }
  return ctxt->write_str(ctxt->user_data, buffer, len);
}



/*---------------------------------------------------------------------------*/
#if (HAVE_DOUBLE > 0)

// just use double always, since va_args pass doubles only
#define PRINTF_USE_DOUBLE_INTERNALLY         1

#if PRINTF_USE_DOUBLE_INTERNALLY
typedef double floating_point_t;
#else
typedef float  floating_point_t;
#endif

static inline int get_sign_bit(floating_point_t x);



// size of the fixed (on-stack) buffer for printing individual decimal numbers.
// this must be big enough to hold one converted floating-point value including
// padded zeros.
#ifndef PRINTF_DECIMAL_BUFFER_SIZE
#define PRINTF_DECIMAL_BUFFER_SIZE    32
#endif

typedef FormatFlags printf_flags_t;
typedef int                printf_size_t;

// @return len printed to buf
static
unsigned print_floating_point(char* buf, floating_point_t value
                        , int precision, unsigned width
                        , printf_flags_t flags);

#endif  //#if (HAVE_DOUBLE

#define NUM_DECIMAL_DIGITS_IN_INT64_T 18

// Note: This value does not mean that all floating-point values printed with the
// library will be correct up to this precision; it is just an upper-bound for
// avoiding buffer overruns and such
#define PRINTF_MAX_SUPPORTED_PRECISION (NUM_DECIMAL_DIGITS_IN_INT64_T - 1)

#if (HAVE_DOUBLE & HAVE_DOUBLE_EXP) != 0

#define PRINTF_SUPPORT_EXPONENTIAL_SPECIFIERS   1
#define PRINTF_SUPPORT_DECIMAL_SPECIFIERS       1

#endif



/*---------------------------------------------------------------------------*/
int
format_str(const strformat_context_t *ctxt, const char *format, ...)
{
  int ret;
  va_list ap;
  va_start(ap, format);
  ret = format_str_v(ctxt, format, ap);
  va_end(ap);
  return ret;
}
/*---------------------------------------------------------------------------*/
struct FormatCtx {
    const strformat_context_t *ctxt;
    FormatFlags     flags;
    unsigned int    minwidth;
    int             precision; /* Negative means no precision */
    unsigned int    width;
    int             negative;

    char *          prefix;               /* sign, "0x" or "0X" */
    unsigned int    prefix_len;

    char *          conv_pos;
    unsigned int    conv_len;
};

int output_fctx( struct FormatCtx* self ){
    const strformat_context_t *ctxt = self->ctxt;

    int written = 0;
    unsigned int precision_fill;
    unsigned int field_fill;

    self->width += self->conv_len;

    if (self->prefix == NULL){
        self->prefix_len = 0;

        if(  (self->flags & (RADIX_MASK | ALTERNATE_FORM))
                == (RADIX_HEX | ALTERNATE_FORM)
          )
        {
          self->prefix_len = 2;
          if(self->flags & CAPS_YES) {
              self->prefix = "0X";
          } else {
              self->prefix = "0x";
          }
        }

    }

    char csign = '\0';
    if(self->flags & SIGNED_YES) {
      if(self->negative) {
          csign = '-';
          ++self->width;
      } else {
        switch(self->flags & POSITIVE_MASK) {
        case POSITIVE_SPACE:
            csign = ' ';
            ++self->width;
            break;
        case POSITIVE_PLUS:
            csign = '+';
            ++self->width;
            break;
        }
      }
    }

    self->width += self->prefix_len;

    if ( self->precision > (int)self->conv_len )
        precision_fill =  self->precision - self->conv_len;
    else
        precision_fill = 0;

    if( (self->flags & (RADIX_MASK | ALTERNATE_FORM)) == (RADIX_OCTAL | ALTERNATE_FORM))
    {
      if(precision_fill < 1) {
        precision_fill = 1;
      }
    }

    self->width += precision_fill;

    field_fill = 0;
    if (self->minwidth > self->width)
        field_fill = self->minwidth - self->width;

    if (field_fill > 0)
    if((self->flags & JUSTIFY_MASK) == JUSTIFY_RIGHT) {
      if(self->flags & PAD_ZERO) {
        precision_fill += field_fill;
        field_fill = 0; /* Do not double count padding */
      } else {
        CHECKCB(fill_space(ctxt, field_fill));
        written += field_fill;
      }
    }

    if (csign){
      CHECKCB(ctxt->write_str(ctxt->user_data, &csign, 1));
      ++written;
    }

    if(self->prefix_len > 0) {
      CHECKCB(ctxt->write_str(ctxt->user_data, self->prefix, self->prefix_len));
      written += self->prefix_len;
    }

    if (precision_fill > 0) {
        CHECKCB(fill_zero(ctxt, precision_fill));
        written += precision_fill;
    }

    CHECKCB(ctxt->write_str(ctxt->user_data, self->conv_pos, self->conv_len));
    written += self->conv_len;

    if (field_fill > 0)
    if((self->flags & JUSTIFY_MASK) == JUSTIFY_LEFT) {
      CHECKCB(fill_space(ctxt, field_fill));
      written += field_fill;
    }

    return written;
}
/*---------------------------------------------------------------------------*/
int
format_str_v(const strformat_context_t *ctxt, const char *format, va_list ap)
{
  unsigned int written = 0;
  const char *pos = format;
  struct FormatCtx self;
  self.ctxt = ctxt;

  while(*pos != '\0') {
      self.precision= -1; /* Negative means no precision */
      self.minwidth = 0;
      self.width    = 0;
      self.prefix   = NULL;

    char ch;
    const char *start = pos;

    while((ch = *pos) != '\0' && ch != '%') {
      pos++;
    }

    if(pos != start) {
      CHECKCB(ctxt->write_str(ctxt->user_data, start, pos - start));
      written += pos - start;
    }

    if(*pos == '\0') {
      return written;
    }

    pos++;

    if(*pos == '\0') {
      return written;
    }

    self.flags = parse_flags(&pos);

    /* parse width */
    if(*pos >= '1' && *pos <= '9') {
        self.minwidth = parse_uint(&pos);
    } else if(*pos == '*') {
      int w = va_arg(ap, int);

      if(w < 0) {
          self.flags |= JUSTIFY_LEFT;
          self.minwidth = w;
      } else {
          self.minwidth = w;
      }

      pos++;
    }

    /* parse precision */
    if(*pos == '.') {
      pos++;

      if(*pos >= '0' && *pos <= '9') {
        self.precision = parse_uint(&pos);
      } else if(*pos == '*') {
        pos++;
        self.precision = va_arg(ap, int);
      }
    }

    if(*pos == 'l') {
      pos++;

      if(*pos == 'l') {
        self.flags |= SIZE_LONGLONG;
        pos++;
      } else {
        self.flags |= SIZE_LONG;
      }
    } else if(*pos == 'h') {
      pos++;

      if(*pos == 'h') {
        self.flags |= SIZE_CHAR;
        pos++;
      } else {
        self.flags |= SIZE_SHORT;
      }
    } else if(*pos == 'z') {
      if(sizeof(size_t) == sizeof(short)) {
        self.flags |= SIZE_SHORT;
      } else if(sizeof(size_t) == sizeof(long)) {
        self.flags |= SIZE_LONG;
      }
#if HAVE_LONGLONG
      else if(sizeof(size_t) == sizeof(long long)) {
        self.flags |= SIZE_LONGLONG;
      }
#endif
      pos++;
    }

    /* parse conversion specifier */
    switch(*pos) {
    case 'd':
    case 'i':
      self.flags |= CONV_INTEGER | RADIX_DECIMAL | SIGNED_YES;
      break;
    case 'u':
      self.flags |= CONV_INTEGER | RADIX_DECIMAL | SIGNED_NO;
      break;
    case 'o':
      self.flags |= CONV_INTEGER | RADIX_OCTAL | SIGNED_NO;
      break;
    case 'x':
      self.flags |= CONV_INTEGER | RADIX_HEX | SIGNED_NO;
      break;
    case 'X':
      self.flags |= CONV_INTEGER | RADIX_HEX | SIGNED_NO | CAPS_YES;
      break;
#if HAVE_DOUBLE

# if (HAVE_DOUBLE & HAVE_DOUBLE_EXP) != 0
    case 'f':
      self.flags |= CONV_FLOAT | FLOAT_NORMAL            | SIGNED_YES;
      break;
    case 'F':
      self.flags |= CONV_FLOAT | FLOAT_NORMAL | CAPS_YES | SIGNED_YES;
      break;
    case 'e':
      self.flags |= CONV_FLOAT | FLOAT_EXPONENT          | SIGNED_YES;
      break;
    case 'E':
      self.flags |= CONV_FLOAT | FLOAT_EXPONENT | CAPS_YES | SIGNED_YES;
      break;
    case 'g':
      self.flags |= CONV_FLOAT | FLOAT_DEPENDANT           | SIGNED_YES;
      break;
    case 'G':
      self.flags |= CONV_FLOAT | FLOAT_DEPENDANT | CAPS_YES | SIGNED_YES;
      break;
# else
      // use HEX printer if not provides normal
    case 'f':
    case 'e':
    case 'g':
        self.flags |= CONV_FLOAT | FLOAT_HEX                 | SIGNED_YES;
        break;

    case 'F':
    case 'E':
    case 'G':
        self.flags |= CONV_FLOAT | FLOAT_HEX | CAPS_YES      | SIGNED_YES;
        break;
# endif

    case 'a':
      self.flags |= CONV_FLOAT | FLOAT_HEX                 | SIGNED_YES;
      break;
    case 'A':
      self.flags |= CONV_FLOAT | FLOAT_HEX | CAPS_YES      | SIGNED_YES;
      break;
#endif
    case 'c':
      self.flags |= CONV_CHAR;
      break;
    case 's':
      self.flags |= CONV_STRING;
      break;
    case 'p':
      self.flags |= CONV_POINTER;
      break;
    case 'n':
      self.flags |= CONV_WRITTEN;
      break;
    case '%':
      self.flags |= CONV_PERCENT;
      break;
    case '\0':
      return written;
    }
    pos++;

    switch(self.flags & CONV_MASK) {
    case CONV_PERCENT:
      CHECKCB(ctxt->write_str(ctxt->user_data, "%", 1));
      written++;
      break;

    case CONV_INTEGER:
    {
      /* unsigned integers */
      char buffer[MAXCHARS];
        self.conv_pos = buffer + MAXCHARS;
        self.conv_len = 0;
      LARGEST_UNSIGNED uvalue = 0;
        self.negative = 0;
        self.prefix_len = 0;

      if(self.precision < 0) {
          self.precision = 1;
      } else {
          self.flags &= ~PAD_ZERO;
      }

      if(self.flags & SIGNED_YES) {
        /* signed integers */
        LARGEST_SIGNED value = 0;
        switch(self.flags & SIZE_MASK) {
        case SIZE_CHAR:
          value = (signed char)va_arg(ap, int);
          break;
        case SIZE_SHORT:
          value = (short)va_arg(ap, int);
          break;
        case SIZE_INT:
          value = va_arg(ap, int);
          break;
#if !HAVE_LONGLONG
        case SIZE_LONGLONG: /* Treat long long the same as long */
#endif
        case SIZE_LONG:
          value = va_arg(ap, long);
          break;
#if HAVE_LONGLONG
        case SIZE_LONGLONG:
          value = va_arg(ap, long long);
          break;
#endif
        }
        if(value < 0) {
          uvalue = -value;
          self.negative = 1;
        } else {
          uvalue = value;
          self.negative = 0;
        }
      } else {

        switch(self.flags & SIZE_MASK) {
        case SIZE_CHAR:
          uvalue = (unsigned char)va_arg(ap, unsigned int);
          break;
        case SIZE_SHORT:
          uvalue = (unsigned short)va_arg(ap, unsigned int);
          break;
        case SIZE_INT:
          uvalue = va_arg(ap, unsigned int);
          break;
#if !HAVE_LONGLONG
        case SIZE_LONGLONG: /* Treat long long the same as long */
#endif
        case SIZE_LONG:
          uvalue = va_arg(ap, unsigned long);
          break;
#if HAVE_LONGLONG
        case SIZE_LONGLONG:
          uvalue = va_arg(ap, unsigned long long);
          break;
#endif
        }

        self.negative = 0;
      }

      if (uvalue == 0) {
          self.flags &= ~ALTERNATE_FORM;
      }

      self.conv_len = output_radix_num(&self.conv_pos, self.flags, uvalue);
      written += output_fctx(&self);
    }
    break;

    case CONV_STRING:
    {
      unsigned int len;
      const char *str = va_arg(ap, const char *);

      if(str) {
        const char *pos = str;
        const char *limit = NULL;
        if ( self.precision >= 0 )
            limit = pos + self.precision;
        while( (*pos != '\0') && (pos != limit) )
            pos++;
        len = pos - str;
      } else {
        str = "(null)";
        len = 6;
      }

      if(self.precision >= 0 && self.precision < (int)len) {
        len = self.precision;
      }
      self.conv_len = len;
      self.conv_pos = (char*)str;
      written += output_fctx(&self);
    }
    break;

    case CONV_POINTER:
    {

#if HAVE_NETADDR
        char buffer[UIPLIB_IPV6_MAX_STR_LEN];

      if ( *pos == 'L' ){           // linkaddr
          ++pos;
          const linkaddr_t* lladdr = (const linkaddr_t *)va_arg(ap, void *);
          if(lladdr == NULL) {
              self.conv_pos = "(LL nil)";
              self.conv_len = 8;
          } else {
              self.conv_pos = buffer + sizeof(buffer)-1;
              self.conv_len = 0;
            unsigned int i;
            const uint8_t* adrch = lladdr->u8 + LINKADDR_SIZE-1;
            for(i = 0; i < LINKADDR_SIZE; ++i, --adrch) {

              if ( (i > 0) && ((i % 2 )== 0) && (LINKADDR_SIZE > 2)) {
                  self.conv_len++;
                *(--self.conv_pos) = '.';
              }

              unsigned olen = output_uint_hex(&self.conv_pos, *adrch, self.flags);
              if ( olen == 0){
                  *(--self.conv_pos) = '0';
                  ++olen;
              }
              if ( olen == 1){
                  *(--self.conv_pos) = '0';
                  ++olen;
              }
              self.conv_len += olen;
            }
          }
      }
#if NETSTACK_CONF_WITH_IPV6
      else if (*pos == 'I'){                         // ipv6
          ++pos;
          const uip_ipaddr_t* ipaddr = (const uip_ipaddr_t *)va_arg(ap, void *);
          self.conv_len = uiplib_ipaddr_snprint(buffer, sizeof(buffer), ipaddr);
          self.conv_pos = buffer;
      }
#endif
      else {
#else
     char buffer[MAXCHARS_HEX + 4];
     {
#endif

          LARGEST_UNSIGNED uvalue = (LARGEST_UNSIGNED)(uintptr_t)va_arg(ap, void *);

          self.conv_pos = buffer + MAXCHARS_HEX + 3;
          self.conv_len = output_uint_hex(&self.conv_pos, uvalue, self.flags);

          if(self.conv_len == 0) {
            self.conv_len = 6;
            if(self.flags & CAPS_YES)
                self.conv_pos = "(NULL)";
            else
                self.conv_pos = "(null)";
          }
          else {
              self.prefix_len = 3;
              if(self.flags & CAPS_YES) {
                  self.prefix = "#0X";
              } else {
                  self.prefix = "#0x";
              }
          }

      }
      written += output_fctx(&self);
    }
    break;

    case CONV_CHAR:
    {
      char ch = va_arg(ap, int);

      self.conv_len = 1;
      self.conv_pos = &ch;
      written += output_fctx(&self);
    }
    break;
    case CONV_WRITTEN:
    {
      int *p = va_arg(ap, int *);
      *p = written;
    }
    break;

#if HAVE_DOUBLE
    case CONV_FLOAT:
    {
        char buf[PRINTF_DECIMAL_BUFFER_SIZE];

        /// va_arg always pass float as double
        floating_point_t value = va_arg(ap, double);

        self.negative = get_sign_bit(value);

        self.conv_pos = buf+ PRINTF_DECIMAL_BUFFER_SIZE-1;

        self.conv_len = print_floating_point(self.conv_pos, value
                                , self.precision, self.minwidth, self.flags);
        self.conv_pos -= self.conv_len;

        if ( (self.flags & FLOAT_MASK) == FLOAT_HEX)
            self.flags |= RADIX_HEX | ALTERNATE_FORM;    // force 0X prefix

        written += output_fctx(&self);
    }
    break;
#endif

    }
  }

  return written;
}

/*---------------------------------------------------------------------------
 * floats print implementation ported from  https://github.com/mpaland/printf.git
 */

// internal flag definitions
#define FLAGS_ZEROPAD   PAD_ZERO
#define FLAGS_LEFT      JUSTIFY_LEFT
#define FLAGS_PLUS      POSITIVE_PLUS
#define FLAGS_SPACE     POSITIVE_SPACE
#define FLAGS_HASH      ALTERNATE_FORM
#define FLAGS_UPPERCASE CAPS_YES
#define FLAGS_SHORT     SIZE_SHORT
#define FLAGS_LONG      SIZE_LONG
#define FLAGS_LONG_LONG SIZE_LONGLONG
#define FLAGS_ADAPT_EXP FLOAT_DEPENDANT



// Default precision for the floating point conversion specifiers (the C standard sets this at 6)
#ifndef PRINTF_DEFAULT_FLOAT_PRECISION
#define PRINTF_DEFAULT_FLOAT_PRECISION  6
#endif

// According to the C languages standard, printf() and related functions must be able to print any
// integral number in floating-point notation, regardless of length, when using the %f specifier -
// possibly hundreds of characters, potentially overflowing your buffers. In this implementation,
// all values beyond this threshold are switched to exponential notation.
#ifndef PRINTF_MAX_INTEGRAL_DIGITS_FOR_DECIMAL
#define PRINTF_MAX_INTEGRAL_DIGITS_FOR_DECIMAL 9
#endif

// The following will convert the number-of-digits into an exponential-notation literal
#define PRINTF_CONCATENATE(s1, s2) s1##s2
#define PRINTF_EXPAND_THEN_CONCATENATE(s1, s2) PRINTF_CONCATENATE(s1, s2)
#define PRINTF_FLOAT_NOTATION_THRESHOLD ((floating_point_t) PRINTF_EXPAND_THEN_CONCATENATE(1e,PRINTF_MAX_INTEGRAL_DIGITS_FOR_DECIMAL))


// The number of terms in a Taylor series expansion of log_10(x) to
// use for approximation - including the power-zero term (i.e. the
// value at the point of expansion).
#ifndef PRINTF_LOG10_TAYLOR_TERMS
#define PRINTF_LOG10_TAYLOR_TERMS 4
#endif

#if PRINTF_LOG10_TAYLOR_TERMS <= 1
#error "At least one non-constant Taylor expansion is necessary for the log10() calculation"
#endif

// Be extra-safe, and don't assume format specifiers are completed correctly
// before the format string end.
#ifndef PRINTF_CHECK_FOR_NUL_IN_FORMAT_SPECIFIER
#define PRINTF_CHECK_FOR_NUL_IN_FORMAT_SPECIFIER 1
#endif



#if HAVE_DOUBLE > 0
#include <float.h>
#if FLT_RADIX != 2
#error "Non-binary-radix floating-point types are unsupported."
#endif

#if PRINTF_USE_DOUBLE_INTERNALLY
#define FP_TYPE_MANT_DIG DBL_MANT_DIG
#else
#define FP_TYPE_MANT_DIG FLT_MANT_DIG
#endif

#if FP_TYPE_MANT_DIG == 24

typedef uint32_t printf_fp_uint_t;
#define FP_TYPE_SIZE_IN_BITS   32
#define FP_TYPE_EXPONENT_MASK  0xFFU
#define FP_TYPE_BASE_EXPONENT  127
#define FP_TYPE_MAX            FLT_MAX
#define FP_TYPE_MAX_10_EXP     FLT_MAX_10_EXP
#define FP_TYPE_MAX_SUBNORMAL_EXPONENT_OF_10 -38
#define FP_TYPE_MAX_SUBNORMAL_POWER_OF_10 1e-38f
#define PRINTF_MAX_PRECOMPUTED_POWER_OF_10  10

#elif FP_TYPE_MANT_DIG == 53

typedef uint64_t printf_fp_uint_t;
#define FP_TYPE_SIZE_IN_BITS   64
#define FP_TYPE_EXPONENT_MASK  0x7FFU
#define FP_TYPE_BASE_EXPONENT  1023
#define FP_TYPE_MAX            DBL_MAX
#define FP_TYPE_MAX_10_EXP     DBL_MAX_10_EXP
#define FP_TYPE_MAX_10_EXP     DBL_MAX_10_EXP
#define FP_TYPE_MAX_SUBNORMAL_EXPONENT_OF_10 -308
#define FP_TYPE_MAX_SUBNORMAL_POWER_OF_10 1e-308
#define PRINTF_MAX_PRECOMPUTED_POWER_OF_10  NUM_DECIMAL_DIGITS_IN_INT64_T - 1


#else
#error "Unsupported floating point type configuration"
#endif
#define FP_TYPE_STORED_MANTISSA_BITS (FP_TYPE_MANT_DIG - 1)

typedef union {
  printf_fp_uint_t  U;
  floating_point_t  F;
} floating_point_with_bit_access;

// This is unnecessary in C99, since compound initializers can be used,
// but:
// 1. Some compilers are finicky about this;
// 2. Some people may want to convert this to C89;
// 3. If you try to use it as C++, only C++20 supports compound literals
static inline floating_point_with_bit_access get_bit_access(floating_point_t x)
{
  floating_point_with_bit_access dwba;
  dwba.F = x;
  return dwba;
}

static inline int get_sign_bit(floating_point_t x)
{
  // The sign is stored in the highest bit
  return (int) (get_bit_access(x).U >> (FP_TYPE_SIZE_IN_BITS - 1));
}

static inline int get_exp2(floating_point_with_bit_access x)
{
  // The exponent in an IEEE-754 floating-point number occupies a contiguous
  // sequence of bits (e.g. 52..62 for 64-bit doubles), but with a non-trivial representation: An
  // unsigned offset from some negative value (with the extremal offset values reserved for
  // special use).
  return (int)((x.U >> FP_TYPE_STORED_MANTISSA_BITS ) & FP_TYPE_EXPONENT_MASK) - FP_TYPE_BASE_EXPONENT;
}
#define PRINTF_ABS(_x) ( (_x) > 0 ? (_x) : -(_x) )



// Stores a fixed-precision representation of a floating-point number relative
// to a fixed precision (which cannot be determined by examining this structure)
struct floating_point_components {
  int_fast64_t integral;
  int_fast64_t fractional;
  int   precision;
    // ... truncation of the actual fractional part of the floating_point_t value, scaled
    // by the precision value
  bool is_negative;
};


static
unsigned print_broken_up_decimal(char* output,
                    struct floating_point_components number_,
                    printf_flags_t flags)
{
    char* buf = output;
    unsigned len = 0;

    int precision = number_.precision;
  if (precision != 0U) {
    // do fractional part, as an unsigned number

    if (precision > PRINTF_DECIMAL_BUFFER_SIZE)
        return 0;

    unsigned count = precision;

    // %g/%G mandates we skip the trailing 0 digits...
    if ((flags & FLAGS_ADAPT_EXP) && !(flags & FLAGS_HASH)
        && (number_.fractional > 0))
    {
        while(true) {
          int_fast64_t digit = number_.fractional % 10U;
          if (digit != 0) {
            break;
          }
          --count;
          number_.fractional /= 10U;

        }
      // ... and even the decimal point if there are no
      // non-zero fractional part digits (see below)
    }

    if (        (number_.fractional > 0)
            || !(flags & FLAGS_ADAPT_EXP)
            || (flags & FLAGS_HASH)
            )
    {
        count -= output_radix_num(&buf, flags, number_.fractional );

      // add extra 0s
      for (; count > 0U; --count) {
        *(--buf) = '0';
      }
      *(--buf) = '.';
    }
  }
  else {
    if ((flags & FLAGS_HASH)) {
      *(--buf) = '.';
    }
  }

  // Write the integer part of the number (it comes after the fractional
  // since the character order is reversed)
  output_radix_num(&buf, flags, number_.integral );

  len = output - buf;
  if (len <= PRINTF_DECIMAL_BUFFER_SIZE)
      return len;
  else
      return 0;
}

#endif // HAVE_DOUBLE > 0

#if (PRINTF_SUPPORT_DECIMAL_SPECIFIERS || PRINTF_SUPPORT_EXPONENTIAL_SPECIFIERS)

static const floating_point_t powers_of_10[PRINTF_MAX_PRECOMPUTED_POWER_OF_10 + 1] = {
  1e00, 1e01, 1e02, 1e03, 1e04, 1e05, 1e06, 1e07, 1e08, 1e09, 1e10
#if PRINTF_MAX_PRECOMPUTED_POWER_OF_10 > 10
  , 1e11, 1e12, 1e13, 1e14, 1e15, 1e16, 1e17
#endif
};


static
void assign_fraction(struct floating_point_components* y
                            , floating_point_t remainder, printf_size_t precision)
{
    y->fractional = (int_fast64_t)remainder; // when precision == 0, the assigned value should be 0
    remainder -= (floating_point_t) y->fractional; //when precision == 0, this will not change scaled_remainder
    const floating_point_t one_half = 0.5;

    y->fractional += (remainder >= one_half);
    if (remainder == one_half) {
      // banker's rounding: Round towards the even number (making the mean error 0)
        y->fractional &= ~((int_fast64_t) 0x1);
    }
    // handle rollover, e.g. the case of 0.99 with precision 1 becoming (0,100),
    // and must then be corrected into (1, 0).
    // Note: for precision = 0, this will "translate" the rounding effect from
    // the fractional part to the integral part where it should actually be
    // felt (as prec_power_of_10 is 1)
    if ((floating_point_t) y->fractional >= powers_of_10[precision]) {
        y->fractional = 0;
      ++(y->integral);
    }
}

// Break up a floating-point number - which is known to be a finite non-negative number -
// into its base-10 parts: integral - before the decimal point, and fractional - after it.
// Taken the precision into account, but does not change it even internally.
static struct floating_point_components get_components(floating_point_t number, printf_size_t precision)
{
  struct floating_point_components number_;
  number_.is_negative = get_sign_bit(number);
  floating_point_t abs_number = (number_.is_negative) ? -number : number;
  number_.integral = (int_fast64_t) abs_number;
  number_.precision = precision;
  floating_point_t prec_power_of_10 = powers_of_10[precision];

  floating_point_t scaled_remainder = (abs_number - (floating_point_t) number_.integral) * prec_power_of_10;
  assign_fraction(&number_, scaled_remainder, precision);
  return number_;
}

#if PRINTF_SUPPORT_EXPONENTIAL_SPECIFIERS
struct scaling_factor {
  floating_point_t raw_factor;
  bool multiply; // if true, need to multiply by raw_factor; otherwise need to divide by it
};

static floating_point_t apply_scaling(floating_point_t num, struct scaling_factor normalization)
{
  return normalization.multiply ? num * normalization.raw_factor : num / normalization.raw_factor;
}

static floating_point_t unapply_scaling(floating_point_t normalized, struct scaling_factor normalization)
{
#ifdef __GNUC__
// accounting for a static analysis bug in GCC 6.x and earlier
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wmaybe-uninitialized"
#endif
  return normalization.multiply ? normalized / normalization.raw_factor : normalized * normalization.raw_factor;
#ifdef __GNUC__
#pragma GCC diagnostic pop
#endif
}

static struct scaling_factor update_normalization(struct scaling_factor sf, floating_point_t extra_multiplicative_factor)
{
  struct scaling_factor result;
  if (sf.multiply) {
    result.multiply = true;
    result.raw_factor = sf.raw_factor * extra_multiplicative_factor;
  }
  else {
    int factor_exp2 = get_exp2(get_bit_access(sf.raw_factor));
    int extra_factor_exp2 = get_exp2(get_bit_access(extra_multiplicative_factor));

    // Divide the larger-exponent raw raw_factor by the smaller
    if (PRINTF_ABS(factor_exp2) > PRINTF_ABS(extra_factor_exp2)) {
      result.multiply = false;
      result.raw_factor = sf.raw_factor / extra_multiplicative_factor;
    }
    else {
      result.multiply = true;
      result.raw_factor = extra_multiplicative_factor / sf.raw_factor;
    }
  }
  return result;
}

static struct
floating_point_components get_normalized_components(floating_point_t non_normalized
                                            , printf_size_t precision
                                            , struct scaling_factor normalization
                                            , int floored_exp10)
{
  floating_point_t scaled = apply_scaling(non_normalized, normalization);

  bool close_to_representation_extremum = ( (-floored_exp10 + (int) precision) >= FP_TYPE_MAX_10_EXP - 1 );
  if (close_to_representation_extremum) {
    // We can't have a normalization factor which also accounts for the precision, i.e. moves
    // some decimal digits into the mantissa, since it's unrepresentable, or nearly unrepresentable.
    // So, we'll give up early on getting extra precision...
    return get_components(scaled, precision);
  }

  struct floating_point_components components;
  components.is_negative = get_sign_bit(non_normalized);
  non_normalized = (components.is_negative) ? -non_normalized : non_normalized;
  components.precision = precision;

  components.integral = (int_fast64_t)scaled;
  if (components.is_negative)
      components.integral = -components.integral;

  floating_point_t remainder = non_normalized - unapply_scaling((floating_point_t) components.integral, normalization);

  floating_point_t prec_power_of_10 = powers_of_10[precision];
  struct scaling_factor account_for_precision = update_normalization(normalization, prec_power_of_10);
  floating_point_t scaled_remainder = apply_scaling(remainder, account_for_precision);

  assign_fraction(&components, scaled_remainder, precision);
  return components;
}
#endif // PRINTF_SUPPORT_EXPONENTIAL_SPECIFIERS

// internal ftoa for fixed decimal floating point
static unsigned print_decimal_number(char* output, floating_point_t number
                                , int precision, printf_flags_t flags
                                )
{
  struct floating_point_components value_ = get_components(number, precision);
  return print_broken_up_decimal(output, value_, flags);
}



#if PRINTF_SUPPORT_EXPONENTIAL_SPECIFIERS

// A floor function - but one which only works for numbers whose
// floor value is representable by an int.
static int bastardized_floor(floating_point_t x)
{
  if (x >= 0) { return (int) x; }
  int n = (int) x;
  return ( ((floating_point_t) n) == x ) ? n : n-1;
}

// Computes the base-10 logarithm of the input number - which must be an actual
// positive number (not infinity or NaN, nor a sub-normal)
static floating_point_t log10_of_positive(floating_point_t positive_number)
{
  // The implementation follows David Gay (https://www.ampl.com/netlib/fp/dtoa.c).
  //
  // Since log_10 ( M * 2^x ) = log_10(M) + x , we can separate the components of
  // our input number, and need only solve log_10(M) for M between 1 and 2 (as
  // the base-2 mantissa is always 1-point-something). In that limited range, a
  // Taylor series expansion of log10(x) should serve us well enough; and we'll
  // take the mid-point, 1.5, as the point of expansion.

  floating_point_with_bit_access dwba = get_bit_access(positive_number);
  // based on the algorithm by David Gay (https://www.ampl.com/netlib/fp/dtoa.c)
  int exp2 = get_exp2(dwba);
  // drop the exponent, so dwba.F comes into the range [1,2)
  dwba.U = (dwba.U & (((printf_fp_uint_t) (1) << FP_TYPE_STORED_MANTISSA_BITS) - 1U)) |
           ((printf_fp_uint_t) FP_TYPE_BASE_EXPONENT << FP_TYPE_STORED_MANTISSA_BITS);
  floating_point_t z = (dwba.F - (floating_point_t) 1.5);
  return (
    // Taylor expansion around 1.5:
              (floating_point_t) 0.1760912590556812420           // Expansion term 0: ln(1.5)            / ln(10)
    + z     * (floating_point_t) 0.2895296546021678851 // Expansion term 1: (M - 1.5)   * 2/3  / ln(10)
#if PRINTF_LOG10_TAYLOR_TERMS > 2
    - z*z   * (floating_point_t) 0.0965098848673892950 // Expansion term 2: (M - 1.5)^2 * 2/9  / ln(10)
#if PRINTF_LOG10_TAYLOR_TERMS > 3
    + z*z*z * (floating_point_t) 0.0428932821632841311 // Expansion term 2: (M - 1.5)^3 * 8/81 / ln(10)
#endif
#endif
    // exact log_2 of the exponent x, with logarithm base change
    + (floating_point_t) exp2 * (floating_point_t) 0.30102999566398119521 // = exp2 * log_10(2) = exp2 * ln(2)/ln(10)
  );
}


static floating_point_t pow10_of_int(int floored_exp10)
{
  // A crude hack for avoiding undesired behavior with barely-normal or slightly-subnormal values.
  if (floored_exp10 == FP_TYPE_MAX_SUBNORMAL_EXPONENT_OF_10) {
    return FP_TYPE_MAX_SUBNORMAL_POWER_OF_10;
  }
  // Compute 10^(floored_exp10) but (try to) make sure that doesn't overflow
  floating_point_with_bit_access dwba;
  int exp2 = bastardized_floor((floating_point_t) (floored_exp10 * 3.321928094887362 + 0.5));
  const floating_point_t z  = (floating_point_t) (floored_exp10 * 2.302585092994046 - exp2 * 0.6931471805599453);
  const floating_point_t z2 = z * z;
  dwba.U = ((printf_fp_uint_t)(exp2) + FP_TYPE_BASE_EXPONENT) << FP_TYPE_STORED_MANTISSA_BITS;
  // compute exp(z) using continued fractions,
  // see https://en.wikipedia.org/wiki/Exponential_function#Continued_fractions_for_ex
  dwba.F *= 1 + 2 * z / (2 - z + (z2 / (6 + (z2 / (10 + z2 / 14)))));
  return dwba.F;
}

static
unsigned print_exponential_number(char* output, floating_point_t number
                            , int precision, unsigned width
                            , printf_flags_t flags
                            )
{
  const bool negative = get_sign_bit(number);
  // This number will decrease gradually (by factors of 10) as we "extract" the exponent out of it
  floating_point_t abs_number =  negative ? -number : number;

  int floored_exp10;
  bool abs_exp10_covered_by_powers_table;
  struct scaling_factor normalization;


  // Determine the decimal exponent
  if (abs_number == (floating_point_t) 0.0) {
    // TODO: This is a special-case for 0.0 (and -0.0); but proper handling is required for denormals more generally.
    floored_exp10 = 0; // ... and no need to set a normalization factor or check the powers table

    normalization.raw_factor = 1.;      // fix warning -Wmaybe-uninitialized
  }
  else  {
    floating_point_t exp10 = log10_of_positive(abs_number);
    floored_exp10 = bastardized_floor(exp10);
    floating_point_t p10 = pow10_of_int(floored_exp10);
    // correct for rounding errors
    if (abs_number < p10) {
      floored_exp10--;
      p10 /= 10;
    }

    abs_exp10_covered_by_powers_table = PRINTF_ABS(floored_exp10) < PRINTF_MAX_PRECOMPUTED_POWER_OF_10;
    if (abs_exp10_covered_by_powers_table)
        normalization.raw_factor = powers_of_10[PRINTF_ABS(floored_exp10)];
    else
        normalization.raw_factor = p10;
  }

#ifdef __GNUC__
// accounting for a static analysis bug in GCC 6.x and earlier
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wmaybe-uninitialized"
#endif
  normalization.multiply = (floored_exp10 < 0 && abs_exp10_covered_by_powers_table);
#ifdef __GNUC__
#pragma GCC diagnostic pop
#endif

  // We now begin accounting for the widths of the two parts of our printed field:
  // the decimal part after decimal exponent extraction, and the base-10 exponent part.
  // For both of these, the value of 0 has a special meaning, but not the same one:
  // a 0 exponent-part width means "don't print the exponent"; a 0 decimal-part width
  // means "use as many characters as necessary".

  bool fall_back_to_decimal_only_mode = false;
  if (flags & FLAGS_ADAPT_EXP) {
    int required_significant_digits = (precision <= 0) ? 1 : (int) precision;
    // Should we want to fall-back to "%f" mode, and only print the decimal part?
    fall_back_to_decimal_only_mode = (floored_exp10 >= -4)
                                    && (floored_exp10 < required_significant_digits);
    // Now, let's adjust the precision
    // This also decided how we adjust the precision value - as in "%g" mode,
    // "precision" is the number of _significant digits_, and this is when we "translate"
    // the precision value to an actual number of decimal digits.

    // the presence of the exponent ensures only one significant digit comes before the decimal point
    precision = (int) precision - 1;
    if ( fall_back_to_decimal_only_mode )
         precision -= floored_exp10;

    if (precision < 0)
        precision = 0;
  }

  bool should_skip_normalization = (fall_back_to_decimal_only_mode || floored_exp10 == 0);
  struct floating_point_components decimal_part_components =
    should_skip_normalization ?
    get_components(number, precision) :
    get_normalized_components(number, precision, normalization, floored_exp10);

  // Account for roll-over, e.g. rounding from 9.99 to 100.0 - which effects
  // the exponent and may require additional tweaking of the parts
  if (fall_back_to_decimal_only_mode) {
    if ((flags & FLAGS_ADAPT_EXP)
        && floored_exp10 >= -1
        && decimal_part_components.integral == powers_of_10[floored_exp10 + 1]
        )
    {
      floored_exp10++; // Not strictly necessary, since floored_exp10 is no longer really used
      if (precision > 0U) { precision--; }
      // ... and it should already be the case that decimal_part_components.fractional == 0
    }
    // TODO: What about rollover strictly within the fractional part?
  }
  else {
    if (decimal_part_components.integral >= 10) {
      floored_exp10++;
      decimal_part_components.integral = 1;
      decimal_part_components.fractional = 0;
    }
  }


  char* buf = output;
  unsigned len = 0;
  if (! fall_back_to_decimal_only_mode) {
    len = output_uint_decimal(&buf, ABS(floored_exp10) );
    *(--buf) = (floored_exp10 >= 0)? '+' : '-';
    *(--buf) = (flags & FLAGS_UPPERCASE)? 'E' : 'e';
    len += 2;
  }

  len += print_broken_up_decimal(buf, decimal_part_components, flags );
  return len;
}
#endif  // PRINTF_SUPPORT_EXPONENTIAL_SPECIFIERS
#endif  // (PRINTF_SUPPORT_DECIMAL_SPECIFIERS || PRINTF_SUPPORT_EXPONENTIAL_SPECIFIERS)


#if HAVE_DOUBLE > 0

static
unsigned print_hex_float(char* output, floating_point_t value
                        , int precision, printf_flags_t flags)
{
    struct floating_point_components number_;
    enum {
        ALIGNED_MANTISSA_BITS = (FP_TYPE_STORED_MANTISSA_BITS-4),
        FP_MANTISSA_MASK       = (1ull <<(FP_TYPE_STORED_MANTISSA_BITS-1))-1,
    };

    number_.is_negative = 0; //get_sign_bit(value);
    //floating_point_t abs_number = (number_.is_negative) ? -value : value;
    number_.fractional = get_bit_access(value).U & FP_MANTISSA_MASK;
    int exp2 = get_exp2( get_bit_access(value) );

    if ((flags & FLAGS_HASH) == 0){
        if ( exp2 > (-FP_TYPE_BASE_EXPONENT) ){
            // prints as comma aligned 0xX.xxFEP(n-3)
            number_.integral   = (number_.fractional >> ALIGNED_MANTISSA_BITS) | 8;
            number_.fractional = (number_.fractional << 3) & FP_MANTISSA_MASK;
            exp2 -= 3;
        }
        else {
            number_.integral   = 0;
            if (number_.fractional == 0)
                exp2 = 0;
            else
                ++exp2;     // subnormal number
        }
    }
    else {
        // prints as origin 0x1.xxFEPn
        number_.integral   = 1;
    };

    if (precision < 0)
        precision = 0;

    number_.precision = FP_TYPE_STORED_MANTISSA_BITS/4;
    while ((number_.fractional & 0xf) == 0){
        if (number_.precision <= precision)
            break;
        --number_.precision;
        number_.fractional = number_.fractional >>4;
    }

    // print binary Exponent
    unsigned len = output_uint_decimal(&output, ABS(exp2) );
    *(--output) = (exp2 >= 0)? '+' : '-';
    *(--output) = (flags & FLAGS_UPPERCASE)? 'P' : 'p';
    len += 2;

    flags |= RADIX_HEX;
    if (number_.precision > 0)
        flags |= FLAGS_HASH;

    return len + print_broken_up_decimal(output, number_, flags);
}

static
unsigned print_floating_point(char* output, floating_point_t value
                        , int precision, unsigned width
                        , printf_flags_t flags)
{
  // test for special values
  if (value != value) {
      output -= 3;
      memcpy(output, (flags & FLAGS_UPPERCASE)? "NAN": "nan" , 3);
      return 3;
  }
  if (value < -FP_TYPE_MAX) {
      output -= 4;
      memcpy(output, (flags & FLAGS_UPPERCASE)? "-INF": "-inf" , 4);
      return 4;
  }
  if (value > FP_TYPE_MAX) {
      output -= 3;
      memcpy(output, (flags & FLAGS_UPPERCASE)? "INF": "inf" , 3);
      if (flags & FLAGS_PLUS){
          output[-1] = '+';
          return 4;
      }
      else
          return 3;
  }


#if (HAVE_DOUBLE & HAVE_DOUBLE_EXP) != 0
  if ( (flags & FLOAT_MASK) != FLOAT_HEX)
  {
      bool prefer_exponential = (flags & (FLOAT_DEPENDANT | FLOAT_EXPONENT)) != 0;
      if ( !prefer_exponential )
      {
        // The required behavior of standard printf is to print _every_ integral-part digit -- which could mean
        // printing hundreds of characters, overflowing any fixed internal buffer and necessitating a more complicated
        // implementation.
          prefer_exponential = (value > PRINTF_FLOAT_NOTATION_THRESHOLD)
                             || (value < -PRINTF_FLOAT_NOTATION_THRESHOLD)
                             ;
      }

      // set default precision, if not set explicitly
      if ( precision < 0 ) {
        precision = PRINTF_DEFAULT_FLOAT_PRECISION;
      }

      flags |= RADIX_DECIMAL;

    #if PRINTF_SUPPORT_EXPONENTIAL_SPECIFIERS
      if (prefer_exponential)
        return print_exponential_number(output, value, precision, width, flags);
      else
    #endif
        return print_decimal_number(output, value, precision, flags);
  }
  else
#endif
  {
      return print_hex_float(output, value, precision, flags);
  }

}

#endif



/*---------------------------------------------------------------------------*/
#include <stdio.h>

static strformat_result
write_str(void *user_data, const char *data, unsigned int len)
{
  for (; len > 0; --len) {
    putchar( *data++ );
  }
  return STRFORMAT_OK;
}
/*---------------------------------------------------------------------------*/
static strformat_context_t ctxt =
{
  write_str,
  NULL
};
/*---------------------------------------------------------------------------*/
int
printfck(const char *fmt, ...)
{
  int res;
  va_list ap;
  va_start(ap, fmt);
  res = format_str_v(&ctxt, fmt, ap);
  va_end(ap);
  return res;
}
/*---------------------------------------------------------------------------*/
