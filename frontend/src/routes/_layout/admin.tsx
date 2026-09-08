import { createFileRoute, Outlet } from "@tanstack/react-router"

import { requireRoles } from "@/lib/routeGuards"

export const Route = createFileRoute("/_layout/admin")({
  component: AdminLayout,
  beforeLoad: requireRoles({ allowed: ["ADMIN"], redirectTo: "/" }),
})

function AdminLayout() {
  return <Outlet />
}
