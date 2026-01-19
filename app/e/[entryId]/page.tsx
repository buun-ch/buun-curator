import { redirect } from "next/navigation";

interface ShortEntryUrlPageProps {
  params: Promise<{ entryId: string }>;
}

/** Short URL redirect - redirects /e/:entryId to /feeds/e/:entryId. */
export default async function ShortEntryUrlPage({
  params,
}: ShortEntryUrlPageProps) {
  const { entryId } = await params;
  redirect(`/feeds/e/${entryId}`);
}
