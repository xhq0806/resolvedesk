// 页脚只保留 ResolveDesk 自身的产品标识，不再链接到上游模板社交账号。by AI.Coding
export function Footer() {
  const currentYear = new Date().getFullYear()

  return (
    <footer className="border-t px-6 py-4">
      <p className="text-center text-sm text-muted-foreground">
        ResolveDesk - {currentYear}
      </p>
    </footer>
  )
}
