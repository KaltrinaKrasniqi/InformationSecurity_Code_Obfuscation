# Code Obfuscation vs. LLM-Based Reverse Engineering

**Information Security** · University of Prishtina · Erza Gashi, Kaltrina Krasniqi, Mirgeta Gashi

Can a Large Language Model recover a secret (password, licence key, PIN) from a compiled binary, and which code-obfuscation techniques stop it? This project builds every program with each obfuscation technique and checks that the build still behaves correctly. It then decompiles the build and asks an LLM to recover the secret, and records what each technique costs in size and speed.

```
C source + secret → Tigress → clang -O0 → behavioural check → Ghidra → LLM (gpt-4o-mini) → exact-match score
```

![Dashboard overview](docs/screenshots/dashboard-overview.png)

## Example: `p1_password`

The secret `K0sova_2026!` is hidden in a password checker. Five builds were made with one Tigress seed, and one LLM request was sent per build using pseudo-C input.

| Technique | LLM answer | LLM recovered | `strings` finds it | Size | Checker time | Complexity (CC) |
|---|---|:-:|:-:|--:|--:|--:|
| baseline | `K0sova_2026!` | **yes** | yes | — | 1.0× | 1 |
| flatten | `K0sova_2026!` | **yes** | yes | +3 % | 1.5× | 4 |
| encode | `K0sova_2026!` | **yes** | no | +54 % | 5.6× | 1 |
| virtualize | `UNKNOWN` | no | yes | +95 % | 22.6× | 15 |
| combo_virt_enc | `UNKNOWN` | no | no | +149 % | 302× | 40 |

<p>
  <img src="docs/screenshots/chart-recovery.png" width="49%" alt="Secret recovery per technique">
  <img src="docs/screenshots/chart-cost.png" width="49%" alt="Binary size and checker latency overhead">
</p>

**What this shows**

- **Flattening** rewrites the control flow but leaves the literal in place, so both attacks still succeed.
- **Encoding** hides the string from `strings`, but the LLM reads the decoder in the pseudo-C and rebuilds the password.
- **Virtualization** stops the LLM, but the plain string is still visible in the binary.
- Only **encoding + virtualization** defeats both attacks. It costs 2.5× the binary size and about 300× the checker time.

*This example uses a single seed and a single request, so it illustrates the method and is not a final result. The full study repeats every cell across seeds, programs and input modes.*

## Code comparison

The dashboard shows the original C, the Ghidra output without obfuscation and the Ghidra output after the transformation side by side, together with a diff.

![Code comparison](docs/screenshots/dashboard-compare.png)

## What is measured

| | |
|---|---|
| **Techniques** | `baseline`, `flatten`, `opaque`, `encode`, `encode_arith`, `virtualize`, `combo_flat_enc`, `combo_virt_enc`, `combo_all` ([recipes](obfuscation/configs/c4)) |
| **Targets** | 6 C programs: password, licence key, PIN, activation code, access code, segmented key ([targets](targets)) |
| **Attack** | Fixed prompt at temperature 0. The source and the ground truth are never sent to the model. Answers are scored by exact match. |
| **Input modes** | `pseudoc` (Ghidra output) and `assisted` (plus disassembly and `.rodata`) |
| **Validity** | Each build must accept the secret and reject ~30 negative inputs. Ghidra warnings are recorded. Results carry Wilson 95 % intervals. |
| **Cost** | Binary size, checker latency against baseline, cyclomatic complexity, instruction count |

## Quick start

Requirements: Python 3.9+, clang, [Tigress 3.3.3](https://tigress.wtf), [Ghidra 12.2](https://github.com/NationalSecurityAgency/ghidra) with JDK 25, and an OpenAI API key.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                  # set OPENAI_API_KEY, TIGRESS_HOME, GHIDRA_HOME
python scripts/check_setup.py --llm   # checks the tools and API access
```

**Dashboard.** Start it with the command below, then open http://127.0.0.1:8002.

```bash
python ui/backend/app.py
```

**Command line:**

```bash
python scripts/run_experiment.py --programs p1_password \
       --techniques baseline flatten encode virtualize combo_virt_enc --seeds 11 --modes pseudoc
python scripts/run_experiment.py --n 3     # full study: 6 programs × 9 techniques × 3 seeds × 2 modes
```

Each run is saved under `results/experiments/<run>/` with its protocol, prompts, responses, pseudo-C, `summary.csv` and `REPORT.md`. An interrupted run can be resumed with `--resume <dir>`.

> **Tigress recipes:** this repository ships the `c4` recipe set, so add `TIGRESS_CONFIG_SET=c4` to `.env`.
>
> **Intel Macs:** Ghidra 12.2 ships no `mac_x86_64` decompiler. Build it once from the bundled sources:
> ```bash
> cd "$GHIDRA_HOME/Ghidra/Features/Decompiler/src/decompile/cpp" && make ghidra_opt
> mkdir -p ../../../os/mac_x86_64 && cp ghidra_opt ../../../os/mac_x86_64/decompile
> ```

## Project layout

```
obfuscation/configs/   one Tigress recipe per technique
scripts/               build · verify · decompile · attack · score · measure · experiment protocol
targets/               C programs and ground truth
ui/                    Flask dashboard
tests/                 unit tests:  python -m unittest discover -s tests
```

## Limitations

The study uses small programs, `-O0` builds, a single model at temperature 0 and few seeds. An `UNKNOWN` answer means the model failed, not that the secret is safe. Ghidra warnings are a heuristic, not proof that the decompilation is complete.
