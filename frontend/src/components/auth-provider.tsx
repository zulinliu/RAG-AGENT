"use client";

import React, { useEffect, useState } from "react";
import { isAuthenticated } from "@/lib/auth";
import { usePathname, useRouter } from "next/navigation";
import { Loading } from "@/components/ui/loading";
import { ToastProvider } from "@/components/ui/toast";

interface AuthProviderProps {
  children: React.ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const authenticated = isAuthenticated();
    const publicPaths = ["/login"];

    if (!authenticated && !publicPaths.includes(pathname)) {
      router.replace("/login");
    } else if (authenticated && pathname === "/login") {
      router.replace("/chat");
    }

    setChecked(true);
  }, [pathname, router]);

  if (!checked) {
    return <Loading fullScreen text="加载中..." />;
  }

  return <ToastProvider>{children}</ToastProvider>;
}
