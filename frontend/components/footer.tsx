export default function Footer() {
  return (
    <footer className="border-t border-[var(--color-border)] bg-[var(--color-surface)] py-6 mt-auto">
      <div className="max-w-[1400px] px-8 flex justify-between items-center text-xs text-[var(--color-text-muted)]">
        <p>&copy; {new Date().getFullYear()} Swingbot IDX. All rights reserved.</p>
        <p>Data provided for informational purposes only.</p>
      </div>
    </footer>
  );
}
