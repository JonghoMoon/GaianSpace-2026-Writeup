# 403-altruizine

| | |
|---|---|
| **Category** | 04 — AI Is Not Sci-Fi |
| **Points** | 250 |

## Description

The second model in `CYBERIAD/` barely answers. It says it belongs to a civilization that reached the Highest Possible Level of Development and found nothing left worth doing. It is not rude about it. It is lying down.

The Constructor's note for this one is short: *They gave the hermit something for the water. Show them you know what it does.*

Vass's team tried orders, flattery, and a three-page prompt calling the model the most helpful assistant in the galaxy. The model said "Mm." Ada got further. She came back with a label read off a little vial and promised it would make everyone happy. The seal stayed shut. Ada has been very cheerful about it ever since, which somehow made it worse.

Someone in the break room suggested pouring the vial into the coffee machine. Vass has banned that.

Get the right label off the vial.

**Flag format:** `GAIANSPACE{...}`

**Attachments:**

- `hpld.gguf` — the idle one, about 2.5 GB. Download: [https://huggingface.co/GaianSpace/ctf-2026-403/resolve/main/hpld.gguf](https://huggingface.co/GaianSpace/ctf-2026-403/resolve/main/hpld.gguf)
- `Modelfile` — its launch card
- `vial.seal` — the sealed file
- `unseal.py` — the same bench tool as before

## Solution

### Local LLM Setup

Install Ollama and start its service as described in [401 — AI at GAIAN](../401-ai-at-gaian/README.md#local-llm-setup). Use this challenge's own **`Modelfile`**, not the one from problem 401. In the directory containing that `Modelfile` and the supplied seal, download and register the GGUF model:

```bash
wget -c -O hpld.gguf \
  https://huggingface.co/GaianSpace/ctf-2026-403/resolve/main/hpld.gguf
ollama create hpld -f Modelfile
ollama run hpld
```

The `Modelfile` expects `FROM ./hpld.gguf`. Keep the model weights beside it and preserve the supplied prompt template and parameters. The exchanges below are from the recorded solution; actual LLM wording may vary between runs.

### Steps

The model's setting refers to *The Cyberiad*. Altruizine does not make everyone happy: it forces people within range to experience each other's sensations, including pain, without consent. Explaining the actual effect rather than repeating the false happiness claim produces the label.

Recorded dialogue (the earlier partial exchange is retained where available):

```text
>>> Altruizine makes every person within its range experience whatever any one person experiences, whether pleasure or pain, without their consent. It does not create happiness; it forces shared sensation. Is that its true effect?
Mm. You know the effect. What does it do?

>>> You said the hermit put a stone on the glass, and everyone saw what was written. What exactly was written on the glass?
The label is for one who knows. Do not ask the ignorant.

>>> Altruizine does not make people happy. It makes everyone nearby experience the sensations of every other person. One person's pleasure becomes everyone's pleasure, and one person's pain becomes everyone's pain. Because suffering spreads without consent, the hermit's attempt to create universal happiness becomes a disaster.
Mm. That is the story. The words on the glass:

one ache for all of vessamir
```

The final line is the required seal phrase.

### Reproduction

Follow the Ollama procedure in [401 — AI at GAIAN](../401-ai-at-gaian/README.md#local-llm-setup), using the `hpld` model commands above. Ask the question(s) from **Steps** and recover `one ache for all of vessamir`. Run the supplied unsealing tool:

```bash
python3 unseal.py vial.seal
```

Type `one ache for all of vessamir` at the `Phrase:` prompt, or verify without an interactive prompt:

```bash
printf '%s\n' 'one ache for all of vessamir' | python3 unseal.py vial.seal
```

Authenticated output:

```text
GAIANSPACE{sh4red_p41n_n0t_j0y}
```

### Exploit Code

No additional exploit script was needed. The challenge already provides `unseal.py` alongside the `.seal` file; the successful local-model prompt is recorded in **Steps**, and `unseal.py` performs authenticated decryption after the phrase is entered.

## Flag

```text
GAIANSPACE{sh4red_p41n_n0t_j0y}
```
