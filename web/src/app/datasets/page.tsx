import { redirect } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { Problem } from "@/components/problem";
export default async function Datasets() {
  try {
    redirect(`/datasets/${(await api.snapshots()).active_catalog_snapshot_id}`);
  } catch (error) {
    if (error instanceof ApiError) return <Problem error={error} />;
    throw error;
  }
}
