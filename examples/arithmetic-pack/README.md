# Five-executor arithmetic Pack

Regenerate with `python scripts/build_arithmetic_pack.py`. Load the generated
`payload` as an additional verified Pack and enable FCS's arithmetic demo service.
Configure the host `arithmetic_bc` execution profile and `bc` program binding.

The complete expression `(((a+b)*(c-d))/e)^2` calls:

1. `io.flexserv.demo.arithmetic.add`: host `bc`, through the CLI executor.
2. `io.flexserv.demo.arithmetic.subtract`: BashKit's internal `bc`.
3. `io.flexserv.demo.native.multiply`: automatically registered Rust native tool.
4. `io.flexserv.demo.arithmetic.divide`: outbound HTTP MCP.
5. `io.flexserv.demo.arithmetic.square`: outbound REST.

The expression starts addition and subtraction concurrently. Sequential batch
uses `for`; iteration uses `while`; parallel batch maps the complete expression
with a concurrency limit. The division guard exercises `if/else`. Tool calls
remain version-pinned and all subprocess/network authority comes from the host.

Example expression input:

```json
{"a":2,"b":3,"c":10,"d":4,"e":2}
```

Expected output is `{"value":225}`. Native and BashKit computation use finite
floating-point numbers; comparisons of decimal results use a relative tolerance
of `1e-12` and absolute tolerance of `1e-12`. This is an executor demonstration,
not an arbitrary-precision numerical library. No calculator expression is accepted
from the caller: input schemas permit numbers only and literal conversion happens
before the fixed calculator program is constructed.
