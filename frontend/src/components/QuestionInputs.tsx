// Answer inputs of a timed question (single, multi, numeric with comma decimals, order), shared by the
// legacy verification-test player and the technical-test player. No integrity logic lives here.
import { useState, type DragEvent, type ReactNode } from "react";
import { ArrowDown, ArrowUp, GripVertical } from "lucide-react";
import type { AssessQuestion } from "../api/types";
import { usePrefs } from "../lib/prefs";
import { cx } from "../lib/format";

/** dataTransfer type of the internal drag and drop of an order question */
export const ORDER_DRAG_TYPE = "application/x-te-order";

type Q = Pick<AssessQuestion, "index" | "type" | "options" | "unit">;

/** Answer state of one question: `value()` is what the API expects, `fields` renders the inputs. */
export function useAnswer(q: Q, stemId: string): { ready: boolean; value: () => unknown; fields: ReactNode } {
  const { t } = usePrefs();
  const [single, setSingle] = useState<number | null>(null);
  const [multi, setMulti] = useState<number[]>([]);
  const [numeric, setNumeric] = useState("");
  const [order, setOrder] = useState<number[]>(() => q.options.map((_, i) => i));

  const value = (): unknown => {
    if (q.type === "single") return single;
    if (q.type === "multi") return multi;
    if (q.type === "order") return order;
    const n = Number(numeric.replace(/\s/g, "").replace(",", "."));
    return Number.isFinite(n) ? n : null;
  };
  const ready =
    q.type === "single" ? single !== null : q.type === "multi" ? multi.length > 0 : q.type === "order" ? true : value() !== null && numeric.trim() !== "";

  const fields = (
    <>
      {q.type === "single" && (
        <fieldset className="exam-options" aria-labelledby={stemId}>
          {q.options.map((o, i) => (
            <label key={i} className={cx("exam-option", single === i && "on")}>
              <input type="radio" name={`q${q.index}`} checked={single === i} onChange={() => setSingle(i)} />
              <span>{o}</span>
            </label>
          ))}
        </fieldset>
      )}
      {q.type === "multi" && (
        <fieldset className="exam-options" aria-labelledby={stemId} aria-describedby={`${stemId}-hint`}>
          <p id={`${stemId}-hint`} className="hint">
            {t.test.multiHint}
          </p>
          {q.options.map((o, i) => (
            <label key={i} className={cx("exam-option", multi.includes(i) && "on")}>
              <input
                type="checkbox"
                checked={multi.includes(i)}
                onChange={(e) => setMulti(e.target.checked ? [...multi, i] : multi.filter((x) => x !== i))}
              />
              <span>{o}</span>
            </label>
          ))}
        </fieldset>
      )}
      {q.type === "numeric" && (
        <div className="exam-numeric">
          <label htmlFor={`${stemId}-num`} className="sr-only">
            {t.test.numericPh}
          </label>
          <input
            id={`${stemId}-num`}
            className="input num"
            inputMode="decimal"
            autoComplete="off"
            placeholder={t.test.numericPh}
            value={numeric}
            aria-describedby={`${stemId}-num-h`}
            onChange={(e) => setNumeric(e.target.value.replace(/[^0-9,.\-\s]/g, ""))}
          />
          {q.unit && <span className="exam-unit">{q.unit}</span>}
          <p id={`${stemId}-num-h`} className="hint" style={{ width: "100%" }}>
            {t.test.numericHint}
          </p>
        </div>
      )}
      {q.type === "order" && <OrderList options={q.options} order={order} setOrder={setOrder} />}
    </>
  );
  return { ready, value, fields };
}

/** Keyboard-accessible ordering: drag and drop (internal only) plus up/down buttons and Alt+arrows. */
export function OrderList({ options, order, setOrder }: { options: string[]; order: number[]; setOrder: (o: number[]) => void }) {
  const { t } = usePrefs();
  const [dragging, setDragging] = useState<number | null>(null);
  const move = (from: number, to: number) => {
    if (to < 0 || to >= order.length || from === to) return;
    const next = [...order];
    const [x] = next.splice(from, 1);
    if (x === undefined) return;
    next.splice(to, 0, x);
    setOrder(next);
  };
  return (
    <div className="stack-sm">
      <p className="hint">{t.test.orderHint}</p>
      <ol className="exam-order">
        {order.map((opt, pos) => (
          <li
            key={opt}
            data-order-item
            draggable
            className={cx("exam-order-item", dragging === pos && "is-dragging")}
            onDragStart={(e: DragEvent) => {
              e.dataTransfer.setData(ORDER_DRAG_TYPE, String(pos));
              e.dataTransfer.effectAllowed = "move";
              setDragging(pos);
            }}
            onDragEnd={() => setDragging(null)}
            onDragOver={(e: DragEvent) => {
              if (e.dataTransfer.types.includes(ORDER_DRAG_TYPE)) e.preventDefault();
            }}
            onDrop={(e: DragEvent) => {
              const from = Number(e.dataTransfer.getData(ORDER_DRAG_TYPE));
              if (!Number.isNaN(from)) {
                e.preventDefault();
                move(from, pos);
              }
              setDragging(null);
            }}
          >
            <GripVertical size={16} aria-hidden="true" className="grip" />
            <span className="exam-order-pos num">{pos + 1}</span>
            <span className="exam-order-text">{options[opt]}</span>
            <span className="exam-order-tools">
              <button
                type="button"
                className="btn btn-ghost btn-icon btn-sm"
                aria-label={`${t.common.moveUp} — ${options[opt]} (${t.test.position(pos + 1)})`}
                disabled={pos === 0}
                onClick={() => move(pos, pos - 1)}
                onKeyDown={(e) => e.altKey && e.key === "ArrowUp" && move(pos, pos - 1)}
              >
                <ArrowUp size={15} aria-hidden="true" />
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-icon btn-sm"
                aria-label={`${t.common.moveDown} — ${options[opt]} (${t.test.position(pos + 1)})`}
                disabled={pos === order.length - 1}
                onClick={() => move(pos, pos + 1)}
              >
                <ArrowDown size={15} aria-hidden="true" />
              </button>
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

/** Circular per-question countdown (server-driven remaining seconds). */
export function QuestionTimer({ left, total }: { left: number; total: number }) {
  const { t } = usePrefs();
  const pct = total > 0 ? Math.min(100, (left / total) * 100) : 0;
  const mm = String(Math.floor(left / 60));
  const ss = String(left % 60).padStart(2, "0");
  return (
    <div className={cx("exam-timer", left <= 10 && "is-urgent")} role="timer" aria-label={`${t.test.timeLeft} ${mm}:${ss}`}>
      <svg viewBox="0 0 40 40" aria-hidden="true">
        <circle cx="20" cy="20" r="17" className="et-track" />
        <circle cx="20" cy="20" r="17" className="et-fill" strokeDasharray={2 * Math.PI * 17} strokeDashoffset={2 * Math.PI * 17 * (1 - pct / 100)} />
      </svg>
      <span className="num">
        {mm}:{ss}
      </span>
    </div>
  );
}
