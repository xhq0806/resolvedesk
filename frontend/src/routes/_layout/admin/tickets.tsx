import { createFileRoute, Outlet } from "@tanstack/react-router"

import { requireRoles } from "@/lib/routeGuards"

export const Route = createFileRoute("/_layout/admin/tickets")({
  component: Outlet,
  beforeLoad: requireRoles({ allowed: ["ADMIN"], redirectTo: "/" }),
})
