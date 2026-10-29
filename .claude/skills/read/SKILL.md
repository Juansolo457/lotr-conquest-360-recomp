---
name: read
description: Use before sending a request body to an API or form whose contract you have not read, before shortening a text a person gave you, and when someone asks you to name the newest model or product.
---

# read

Three rules for moments when a quick answer looks right and is wrong. Each rule has a check you run or a question you ask your human, and a clear "done".

The scripts sit in `scripts/` next to this file. Below, `<skill>` is this file's folder. Run the scripts from the working folder: they read files only inside it. They need Node.js 18 or newer and nothing else.

## 1. Before you send a body, find the contract and quote it

**When:** you are about to send a body (POST, PUT, PATCH, a form submit, a webhook call) to an endpoint, and you have not read the shape it accepts.

1. Run `node <skill>/scripts/find-contract.mjs <url>` on the page that pointed you to the endpoint, or on the endpoint itself. It lists what the page declares: `<link>` and HTTP `Link` entries with `rel="service-desc"`, `rel="describedby"` or `rel="service-doc"`, every JSON or YAML `rel="alternate"`, and each `<form>` with its fields and limits. Add `--open` to print each contract it lists.
2. If the page needs a sign-in, the script gets the sign-in page. Ask your human to save the signed-in page into the working folder, then run `node <skill>/scripts/find-contract.mjs page.html --base <its URL>`.
3. Quote the contract in your message before you send: its URL, the required fields, their types and limits, and whether extra keys are allowed. Build the body from that quote, not from what a body like it usually holds.
4. If nothing is declared, ask your human where the contract is. Do not invent a shape, and do not send a guess to learn from the error.

**Done:** your message quotes the contract with its URL, and the body matches it field for field.

## 2. Before you shorten a person's text, keep, count and show every cut

**When:** a person gives you a text (a message, notes, a document) and asks for a shorter version.

1. Write the keep list first: each passage the person wants kept exactly, copied from the original, never retyped. If it is not clear what must stay word for word, ask. Save the original, the short version and the keep list as files in the working folder, for example in `cut/`. In the keep list, a line with only `---` goes between passages.
2. Run `node <skill>/scripts/cut-diff.mjs cut/original.txt cut/short.txt --keep-file cut/keep.txt --max-chars 700` with the person's limit. `--max-words` also works.
3. Fix every `FAIL`. For a keep passage, the script shows the first character that differs and its code point, so a curly quote, a different dash or a line break is visible. Change only those characters and run it again.
4. Before you send or save the short version, show the person the counts, the keep check and the cut list, unless they said to go ahead without it. If they want a cut back, put it back and run the script again.

**Done:** the script prints `result: ok`, and you have shown the person every cut.

## 3. When asked to name the newest model or product: memory first, then a live page

**When:** only when someone asks you to name the newest, latest or most recent model or product. This rule covers that question and no other.

1. Write your memory answer first, with how sure you are: `From memory: <name>. How sure: low, medium or high.` Leave that line as it is: it shows the person how far memory was off.
2. Open a live page from the maker: its model list, release notes, changelog or announcement. Prefer the maker's own page to news or a list someone else keeps.
3. Answer with the name exactly as the maker writes it, the page URL, the date on the page, and one sentence quoted from the page that names it. If the page and your memory differ, give both.
4. Answer what was asked. The newest released model is not always the best-known one, and an announced model is not a released one.
5. If you cannot open a live page, say so. Give the memory answer marked `unchecked`, and ask your human for the page.

**Done:** the answer cites a page you opened in this session, or says plainly that it is unchecked.

## Example

The person pastes a 2,400-character update: "Cut this to 500 characters for the team channel. Keep the paragraph that starts 'Deploy freeze' exactly."

1. The agent saves `cut/original.txt`, copies the Deploy freeze paragraph from that file into `cut/keep.txt`, and writes `cut/short.txt`.
2. `cut-diff.mjs` with `--max-chars 500` prints `result: FAIL`. Under keep 1 it shows `expected ’ U+2019 right single quote, found ' U+0027 apostrophe`.
3. The agent changes that one character and runs the script again: `result: ok`, 14 characters under the limit.
4. It shows the person the counts and the cut list and asks if anything should come back. Then it posts the short version.
