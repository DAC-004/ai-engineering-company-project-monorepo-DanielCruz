interface PageContainerProps {
  children: React.ReactNode;
}

export function PageContainer({ children }: PageContainerProps) {
  return (
    <main className="app-shell-wide flex-1 px-4 py-8 sm:px-6 lg:py-10">
      {children}
    </main>
  );
}
