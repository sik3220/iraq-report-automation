import { expiredSessionCookie, authenticationEnabled, passwordMatches, sessionCookie } from "../../lib/auth";

export const dynamic = "force-dynamic";

function secureRequest(request: Request) {
  return new URL(request.url).protocol === "https:";
}

export async function GET() {
  return Response.json({ authenticated: authenticationEnabled() });
}

export async function POST(request: Request) {
  if (!authenticationEnabled()) {
    return Response.json({ success: false, error: "DASHBOARD_PASSWORD가 설정되지 않았습니다." }, { status: 503 });
  }
  let input: unknown;
  try { input = await request.json(); } catch { return Response.json({ success: false, error: "로그인 요청을 읽지 못했습니다." }, { status: 400 }); }
  const password = input && typeof input === "object" && "password" in input ? input.password : undefined;
  if (!passwordMatches(password)) return Response.json({ success: false, error: "비밀번호가 올바르지 않습니다." }, { status: 401 });
  return new Response(JSON.stringify({ success: true }), { status: 200, headers: { "Content-Type": "application/json", "Set-Cookie": sessionCookie(secureRequest(request)) } });
}

export async function DELETE(request: Request) {
  return new Response(JSON.stringify({ success: true }), { status: 200, headers: { "Content-Type": "application/json", "Set-Cookie": expiredSessionCookie(secureRequest(request)) } });
}


