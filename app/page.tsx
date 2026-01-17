import { redirect } from "next/navigation";

/** Root page - redirects to /feeds. */
export default function Home() {
  redirect("/feeds");
}
