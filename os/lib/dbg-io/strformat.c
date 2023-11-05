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
#ifndef PRINTF_CONF_HAVE_DOUBLE
#define HAVE_DOUBLE     1
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

        if(self->flags & SIGNED_YES) {
          if(self->negative) {
              self->prefix = "-";
              self->prefix_len = 1;
          } else {
            switch(self->flags & POSITIVE_MASK) {
            case POSITIVE_SPACE:
                self->prefix = " ";
                self->prefix_len = 1;
                break;
            case POSITIVE_PLUS:
                self->prefix = "+";
                self->prefix_len = 1;
                break;
            }
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
    case 'f':
      self.flags |= CONV_FLOAT | FLOAT_NORMAL;
      break;
    case 'F':
      self.flags |= CONV_FLOAT | FLOAT_NORMAL | CAPS_YES;
      break;
    case 'e':
      self.flags |= CONV_FLOAT | FLOAT_EXPONENT;
      break;
    case 'E':
      self.flags |= CONV_FLOAT | FLOAT_EXPONENT | CAPS_YES;
      break;
    case 'g':
      self.flags |= CONV_FLOAT | FLOAT_DEPENDANT;
      break;
    case 'G':
      self.flags |= CONV_FLOAT | FLOAT_DEPENDANT | CAPS_YES;
      break;
    case 'a':
      self.flags |= CONV_FLOAT | FLOAT_HEX;
      break;
    case 'A':
      self.flags |= CONV_FLOAT | FLOAT_HEX | CAPS_YES;
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

      if(  (self.flags & (RADIX_MASK | ALTERNATE_FORM))
              == (RADIX_HEX | ALTERNATE_FORM)
         && uvalue != 0)
      {
        self.prefix_len = 2;
        if(self.flags & CAPS_YES) {
            self.prefix = "0X";
        } else {
            self.prefix = "0x";
        }
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
    }
  }

  return written;
}

/*---------------------------------------------------------------------------*/
