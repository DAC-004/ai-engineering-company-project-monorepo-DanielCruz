# Local deepmerge security patch

This is a private, MIT-licensed derivative of the installed upstream deepmerge4.3.1 bundle. It is not an upstream release. The original license is retained.

GHSA-gcqx-w48m-w2h4/CVE-2026-93753 has no upstream patched version: https://github.com/advisories/GHSA-gcqx-w48m-w2h4 and https://github.com/TehShrike/deepmerge/issues/273.

The narrow patch rejects __proto__/constructor/prototype keys in BOTH copy loops, defines ordinary own properties without invoking the legacy prototype setter, and fails closed on a throwing target lookup. It retains the public merge/all API, array/custom merge behavior and type declarations. Local version4.3.2-healthcore.1 identifies this derivative; it does not claim an upstream fix or merely suppress an advisory. The recorded root and tracker compatibility checks cover the installed package. Remove this fork only after reviewing a real upstream fix and the applicable application checks.

Original published dist/cjs.js SHA256: 2e5160f84a1141bd927264afe4d15766f1e6cf07daef182b37ff53fea121de7d
