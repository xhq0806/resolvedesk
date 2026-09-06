import { createFileRoute } from "@tanstack/react-router"
import { z } from "zod"

import useAuth from "@/hooks/useAuth"

const searchSchema = z.object({
  access: z.enum(["denied"]).optional(),
})

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  validateSearch: searchSchema,
  head: () => ({
    meta: [
      {
        title: "Dashboard - FastAPI Template",
      },
    ],
  }),
})

function Dashboard() {
  const { user: currentUser } = useAuth()
  const { access } = Route.useSearch()

  return (
    <div>
      {access === "denied" && (
        <p className="mb-4 rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          You do not have permission to access that area.
        </p>
      )}
      <div>
        <h1 className="text-2xl truncate max-w-sm">
          Hi, {currentUser?.full_name || currentUser?.email} 👋
        </h1>
        <p className="text-muted-foreground">
          Welcome back, nice to see you again!!!
        </p>
      </div>
    </div>
  )
}
