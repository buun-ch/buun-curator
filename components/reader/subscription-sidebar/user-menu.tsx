"use client";

import { LogOut, ChevronsUpDown } from "lucide-react";
import { useSession, signOut } from "@/lib/auth-client";
import { cn } from "@/lib/utils";
import { useHydrated } from "@/hooks/use-hydrated";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface UserMenuProps {
  collapsed?: boolean;
}

/** Gets initials from a name (e.g., "John Doe" -> "JD"). */
function getInitials(name: string): string {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

/** User menu component displayed at the bottom of the sidebar. */
export function UserMenu({ collapsed }: UserMenuProps) {
  const hydrated = useHydrated();
  const { data: session, isPending } = useSession();

  // Show skeleton during SSR and loading to prevent hydration mismatch
  if (!hydrated || isPending || !session?.user) {
    return (
      <div
        className={cn(
          "flex w-full items-center gap-2 rounded-md px-3 py-1.5",
          collapsed && "justify-center px-0",
        )}
      >
        <Skeleton className="size-8 rounded-full" />
        {!collapsed && (
          <div className="min-w-0 flex-1 space-y-1">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-3 w-32" />
          </div>
        )}
      </div>
    );
  }

  const user = session.user;
  const initials = getInitials(user.name || user.email || "U");

  const handleSignOut = async () => {
    await signOut();
    window.location.href = "/login";
  };

  return (
    <DropdownMenu key="user-menu">
      <DropdownMenuTrigger key="user-menu-trigger" asChild>
        <button
          key="user-menu-trigger-button"
          className={cn(
            "flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-sm select-none hover:bg-accent",
            collapsed && "justify-center px-0",
          )}
        >
          <Avatar className="size-8 border">
            <AvatarImage src={user.image || undefined} alt={user.name || ""} />
            <AvatarFallback className="text-xs">{initials}</AvatarFallback>
          </Avatar>
          {!collapsed && (
            <>
              <div className="min-w-0 flex-1 text-left">
                <div className="truncate font-medium">{user.name}</div>
                <div className="truncate text-xs text-muted-foreground">
                  {user.email}
                </div>
              </div>
              <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" />
            </>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        side="top"
        align="start"
        className="w-[--radix-dropdown-menu-trigger-width] min-w-56"
      >
        <DropdownMenuLabel className="font-normal">
          <div className="flex items-center gap-2">
            <Avatar className="size-8 border">
              <AvatarImage
                src={user.image || undefined}
                alt={user.name || ""}
              />
              <AvatarFallback>{initials}</AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium">{user.name}</div>
              <div className="truncate text-xs text-muted-foreground">
                {user.email}
              </div>
            </div>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={handleSignOut}>
          <LogOut className="mr-2 size-4" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
