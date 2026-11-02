/** Original brand mark: a shield with a check (identity verified). Uses the same colours as the favicon. */
export default function Logo({ className = "brand-logo" }) {
  return (
    <svg className={className} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <path d="M16 2.2 27.5 6.6v8.7c0 7.2-4.9 12.6-11.5 14.5C9.4 27.9 4.5 22.5 4.5 15.3V6.6z" fill="#0b3a5b" />
      <path d="M16 2.2 27.5 6.6v8.7c0 7.2-4.9 12.6-11.5 14.5z" fill="#0b84c6" />
      <path
        d="M10.2 16.2l4.1 4.1 7.6-8.6"
        fill="none"
        stroke="#fff"
        strokeWidth="2.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="25.4" cy="6.4" r="3.1" fill="#f5a300" />
    </svg>
  );
}
