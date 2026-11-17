# Member 4: Educational & Convenience Features

Adds two tabs to Stego Mail (Member 2's website):

- **Learn**: explains how *our* app hides messages: Member 1's image method, Member 2's text method, and the password lock. It includes a **step-by-step walkthrough** that runs the team's real `embed()` / `hide()` code and shows what happened inside (bits, header, busy-area map, the real groups of 7 values before/after, changed pixels, PSNR, reveal).
- **History**: every Send (hide) and Reveal is recorded automatically, with filters, delete, clear and CSV export. The secret message is **never stored**, only its length.

The saved-image library is Member 2's **Gallery** tab (10 built-in pictures plus the user's own). The Learn walkthrough uses the same gallery.

## Files

| File | Purpose |
|---|---|
| `member4.py` | Flask blueprint: Learn API, History API, records Send/Reveal automatically |
| `learn_trace.py` | Runs Member 1's and Member 2's real functions and collects every step for the walkthrough |
| `templates/member4/learn.html` | Learn tab content (shown inside the Tutorial/Learn view) |
| `templates/member4/history.html` | History tab |
| `static/member4.css`, `static/member4.js` | Styling (uses Member 2's colours, accent and dark mode) and page behaviour |
| `tests/test_member4.py` | 10 automated tests |
| `docs/research-similar-apps.md` | Research on similar existing applications |

## How it is connected to Member 2's app
With Member 2's agreement, a few lines were added to her files so the two tabs appear in the website. Nothing of hers was removed except the short "How it works" box, which the Learn section replaces.

- `Member 2/app.py`: adds `Member 4` to the import path, `import member4`, and `member4.init_app(app)` (3 lines).
- `Member 2/templates/index.html`: loads `member4.css` and `member4.js`, renames the Tutorial menu item to **Learn**, adds a **History** menu item and view, and shows the Learn content under the 4 "how to use" steps.
- `Member 2/static/app.js`: adds `history: 'History'` and the "Learn" title to `TITLES` (1 line).

Nothing in Member 1's folder was changed.

## API

| Method and path | Purpose |
|---|---|
| `POST /api/learn/image` | `message`, `gallery` id or `image` upload, optional `password` → full trace |
| `POST /api/learn/text` | `cover`, `message`, optional `password` → full trace |
| `POST /api/learn/check-text` | `text`, optional `password` → is a message hidden in it? |
| `GET /api/history` · `DELETE /api/history/<id>` · `DELETE /api/history` · `GET /api/history.csv` | History |

All routes require sign-in. History is stored in the same SQLite file (`Member 2/data/stego.db`, table `member4_history`) and is deleted when the user deletes their account.

## Run and test
Start the app as described in Member 2's README, then open **Learn** or **History** in the left menu.

```sh
python -m unittest discover -s "Member 4/tests" -v     # from the repository root
```

`learn_trace.py` reads a few internal helpers of Member 1's `image_stego.py` (`_prepare`, `_Spatial`, `_HSEED`, `_HEADER`, `_keys`) to show which pixels were used. If those names change, update `_image_internals()`; the tests will catch it.
