#!/usr/bin/python3
from bcc import BPF

program = r"""
#include <bcc/proto.h>

int hello(struct xdp_md *ctx) {
  void *data = (void *)(long)ctx->data;
  void *data_end = (void *)(long)ctx->data_end;
  u32 len = ctx->data_end - ctx->data;
  bpf_trace_printk("Got a packet %d", len);
  return XDP_PASS;
}
"""

# Loads the C code from a string
b = BPF(text=program)

# Load the function into XDP
fx = b.load_func("hello", BPF.XDP)

# XDP will be the first program hit when a packet is received ingress
BPF.attach_xdp("lo", fx, 0)

# Outputs the trace in the screen
b.trace_print()
