/**
 * Source-text inspection of federated profile and login controls.
 * Not a rendered browser journey and not actual Microsoft IdP success.
 */

import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const trackerRoot = join(__dirname, "..", "..");

const readRequired = (...segments: string[]): string => {
  const relative = join(...segments).replaceAll("\\", "/");
  const absolute = join(trackerRoot, ...segments);
  if (!existsSync(absolute)) {
    throw new Error(`Required source is missing: ${relative}`);
  }
  return readFileSync(absolute, "utf8");
};

describe("federated profile and login controls", () => {
  const profilePage = readRequired("app", "(app)", "account", "profile", "page.tsx");
  const loginScreen = readRequired("components", "auth", "LoginScreen.tsx");
  const linkControls = readRequired("components", "auth", "FederatedLinkControls.tsx");
  const signInButton = readRequired("components", "auth", "MicrosoftSignInButton.tsx");
  const callbackPage = readRequired("app", "auth", "callback", "microsoft", "page.tsx");
  const federatedLib = readRequired("lib", "auth", "federated.ts");

  it("puts Microsoft link and unlink controls on the existing profile", () => {
    expect(profilePage).toContain("FederatedLinkControls");
    expect(linkControls).toContain("Link Microsoft");
    expect(linkControls).toContain("Unlink Microsoft");
    expect(linkControls).toContain("last remaining access method");
  });

  it("renders a last-access-method warning when unlink is blocked", () => {
    expect(linkControls).toContain("federated-link-warning");
    expect(linkControls).toContain(
      "Unlinking Microsoft would remove your last access method",
    );
    expect(linkControls).toContain("The API will refuse this unlink");
    expect(linkControls).toContain("{!status.can_unlink && status.linked ? (");
  });

  it("keeps Microsoft login separate from account creation", () => {
    expect(loginScreen).toContain("MicrosoftSignInButton");
    expect(signInButton).toContain("Sign in with Microsoft");
    expect(signInButton).toContain("does not create a HealthCore user");
    expect(callbackPage).toContain("completeMicrosoftFederated");
    expect(federatedLib).toContain("tx_binding");
    expect(federatedLib).toContain("hc_federated_tx_binding");
    expect(federatedLib).toContain("sessionStorage");
  });
});
