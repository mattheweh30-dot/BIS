# BIS

Website for BIS, a hedge fund running options-based portfolio management strategies.

Current state: **five homepage theme candidates for review.** No theme has been chosen,
and nothing here is ready to publish.

## Review the themes

Open `index.html` locally, or enable GitHub Pages (below) and visit the site root.
The chooser page links into all five.

| Theme | Reference | Character |
|---|---|---|
| [Meridian](themes/meridian/) | Citadel | Deep navy, hairline rules, huge tight sans. Most conservative. |
| [Lattice](themes/lattice/) | Two Sigma | White, visible grid, implied-vol curve above the fold. Most quantitative. |
| [Sovereign](themes/sovereign/) | Blackstone | Navy and stone, brass rules, transitional serif. Most traditional. |
| [Vantage](themes/vantage/) | Original | Asymmetric 7/5 editorial grid, optical serif, deep teal. Most opinionated. |
| [Terminal](themes/terminal/) | Original | Warm black, sodium amber, monospace, exposure board in the hero. Most operational. |

All five carry identical placeholder content, so the comparison is about typography,
colour, density, and structure rather than copy.

## Read this before publishing anything

A public marketing site is a regulated act for a private fund, not just a design
deliverable. Two constraints shaped every page here:

- **SEC Marketing Rule (Rule 206(4)-1).** Advertisements by a registered investment
  adviser are governed by it, including performance presentation, testimonials,
  endorsements, and hypothetical performance. None of these pages contain performance
  figures, a track record, or testimonials — by design, not by omission.
- **Reg D general solicitation.** Publicly advertising a fund can forfeit the Rule
  506(b) safe harbour and create problems for the 3(c)(1) / 3(c)(7) exclusions. This is
  why every theme routes investors to a login wall and an eligibility statement instead
  of describing the offering.

Practical consequences baked into the markup:

- Every number is a bracketed token — `[±XX]% NAV`, `[X.X]× notional`, `[$X.XB]`. They
  are deliberately ugly so a plausible-looking fake figure cannot reach production by
  accident. Search for `[` before any launch; zero hits is the gate.
- `[registration status — to be confirmed by counsel]` appears in every footer. Counsel
  fills that in; do not guess at it.
- `[Full Legal Name] LP`, `[City], [ST]`, and `[YYYY]` are the other repeated tokens.
- Footer links to Form ADV, Form CRS, privacy policy, terms of use, and business
  continuity are stubbed as `#`. Several of those documents are mandatory for a
  registered adviser.
- The volatility curve in Lattice and the exposure board in Terminal are labelled as
  illustrative, and neither displays market data or quotes. Showing real market data
  usually needs an exchange licence.

None of the above is legal advice. Have counsel review the chosen theme before it is
reachable from the public internet.

## Build and hosting

Plain static HTML. No build step, no dependencies, no JavaScript. Each theme page is a
single self-contained file with its CSS inline; typefaces load from Google Fonts.

Preview locally:

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000`.

### Enabling GitHub Pages

This has to be done once in the repository settings — it cannot be set from a commit:

1. Settings → Pages
2. Source: **Deploy from a branch**
3. Branch: pick the branch holding this work, folder `/ (root)`
4. Save, then wait for the first deployment

A `.nojekyll` file is already committed so Jekyll does not process the directory.

## Repository layout

```
index.html              chooser page — working tool, replaced by the real homepage
themes/
  meridian/index.html
  lattice/index.html
  sovereign/index.html
  vantage/index.html
  terminal/index.html
.nojekyll
```

## Next steps, in order

1. Pick a theme. Move its folder contents to the repository root, delete the other four,
   and replace `index.html` with the real homepage.
2. Build the interior pages the nav already points at: Firm, Strategy, Risk, Research,
   Careers, Contact.
3. Decide how the investor login works. A real portal means authentication, document
   storage, and an audit trail — that is a separate system, not a page, and it is where
   the compliance surface gets serious.
4. Replace every bracketed token with counsel-approved content.
5. Point a domain at the Pages deployment and add TLS.
