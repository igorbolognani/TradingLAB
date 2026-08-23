import { getChatGPTUser, chatGPTSignInPath, chatGPTSignOutPath } from "./chatgpt-auth";
import ResearchLab from "./research-lab";
import { headers } from "next/headers";

export const dynamic = "force-dynamic";

export default async function Page() {
  const user = await getChatGPTUser();
  const requestHeaders = await headers();
  const host = requestHeaders.get("host")?.split(":")[0];
  const ownerUserId = process.env.TRADINGLAB_OWNER_USER_ID?.trim();
  const ownerEmail = process.env.TRADINGLAB_OWNER_EMAIL?.trim().toLowerCase();
  const isConfiguredOwner = Boolean(
    user &&
      ((ownerUserId && user.userId === ownerUserId) ||
        (ownerEmail && user.email.toLowerCase() === ownerEmail)),
  );
  const isLocalOwner = !user && (host === "localhost" || host === "127.0.0.1");

  return (
    <ResearchLab
      isOwner={isConfiguredOwner || isLocalOwner}
      viewer={
        user
          ? { displayName: user.displayName, email: user.email }
          : null
      }
      signInHref={chatGPTSignInPath("/")}
      signOutHref={chatGPTSignOutPath("/")}
    />
  );
}
