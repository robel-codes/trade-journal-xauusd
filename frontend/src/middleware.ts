import { NextResponse, type NextRequest } from "next/server";

// Presence check only; the API verifies the token on every request.
export function middleware(req: NextRequest) {
  const hasSession = req.cookies.has("xau_session");
  const isLogin = req.nextUrl.pathname === "/login";
  if (!hasSession && !isLogin) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("next", req.nextUrl.pathname);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = { matcher: ["/((?!api|_next|favicon.ico).*)"] };
