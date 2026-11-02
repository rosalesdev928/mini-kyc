/** Upload -> Reading -> Result. `status` is the state of the onboarding request. */
function stateOf(status, index) {
  if (status === "success") return "done";
  if (status === "loading") return ["done", "active", "todo"][index];
  if (status === "error") return ["done", "error", "todo"][index];
  return ["active", "todo", "todo"][index];
}

const MARK = { done: "✓", error: "!", active: null, todo: null };

export default function Stepper({ t, status }) {
  return (
    <ol className="stepper" aria-label={t.stepsLabel}>
      {t.steps.map((label, index) => {
        const state = stateOf(status, index);
        const working = state === "active" && status === "loading" ? " step-working" : "";
        return (
          <li
            key={label}
            className={`step step-${state}${working}`}
            aria-current={state === "active" ? "step" : undefined}
          >
            <span className="step-dot">{MARK[state] ?? index + 1}</span>
            <span>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
