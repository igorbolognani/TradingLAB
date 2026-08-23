import { alpacaJson, errorResponse, isOwnerRequest } from "../../../../alpaca-direct";

export const dynamic = "force-dynamic";

export async function GET(request: Request): Promise<Response> {
  if (!(await isOwnerRequest(request))) return Response.json({ error: "owner_access_required" }, { status: 403 });
  try {
    const payload = await alpacaJson("/v2/positions");
    return Response.json({ positions: Array.isArray(payload) ? payload : [] });
  } catch (error) {
    return errorResponse(error);
  }
}
