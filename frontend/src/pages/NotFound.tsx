import { Link } from "react-router-dom";
import { Compass } from "lucide-react";
import { useT } from "../lib/prefs";
import { useCrumbs } from "../components/Shell";
import { EmptyState } from "../components/feedback";

export function NotFoundPage() {
  const t = useT();
  useCrumbs([{ label: t.common.notFound }]);
  return (
    <div className="card">
      <EmptyState
        icon={Compass}
        title={t.common.notFound}
        action={
          <Link to="/" className="btn btn-primary">
            {t.common.goHome}
          </Link>
        }
      >
        {t.common.notFoundBody}
      </EmptyState>
    </div>
  );
}
