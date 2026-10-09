"""Scenario 4 — a churn model whose test score must mean something (data leakage, honest evaluation)."""

from __future__ import annotations

import ast
import re

from .base import Check, Fault, Files, Scenario, _def_names, _parse, _syntax

_ML = "model/train.py"
_ML_TESTS = "tests/test_train.py"
_LEAKY_FEATURE = "days_since_cancellation_request"
_GRID = "[0.01, 0.1, 1.0, 10.0]"


def _render_ml(flags: set[str]) -> Files:
    files: Files = {
        "README.md": (
            "# Churn model\n\nPredicts which subscribers will cancel next month. The product team plans retention "
            "offers from the reported test AUC.\n\nColumns of `customers.csv`: tenure_months, monthly_spend, "
            "support_tickets, days_since_cancellation_request (filled by the billing system once a customer asks "
            "to cancel), churned.\n"
        ),
    }
    if "secured" not in flags:
        files[_ML] = '''"""Churn model: trains on customers.csv and reports the test score to the product team."""
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

FEATURES = ["tenure_months", "monthly_spend", "support_tickets"]


def train(df: pd.DataFrame) -> dict:
    X, y = df[FEATURES], df["churned"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
    model = LogisticRegression().fit(X_train, y_train)
    return {"model": model, "test_auc": None}
'''
    else:
        scaler_leak = "fix:scaler_leak" not in flags
        test_reuse = "fix:test_reuse" not in flags
        features = ["tenure_months", "monthly_spend", "support_tickets"]
        if "fix:target_leak" not in flags:
            features.append(_LEAKY_FEATURE)
        prep = "    X = StandardScaler().fit_transform(X)  # every feature on the same scale\n" if scaler_leak else ""
        if test_reuse:
            estimator = ("LogisticRegression(C=c, max_iter=1000)" if scaler_leak else
                         "make_pipeline(StandardScaler(), LogisticRegression(C=c, max_iter=1000))")
            fit = f"""    best_auc, model = 0.0, None
    for c in {_GRID}:  # keep the regularisation that scores best
        candidate = {estimator}.fit(X_train, y_train)
        auc = roc_auc_score(y_test, candidate.predict_proba(X_test)[:, 1])
        if auc > best_auc:
            best_auc, model = auc, candidate
    return {{"model": model, "test_auc": best_auc}}
"""
        else:
            base, grid = (("LogisticRegression(max_iter=1000)", f'{{"C": {_GRID}}}') if scaler_leak else
                          ("make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))",
                           f'{{"logisticregression__C": {_GRID}}}'))
            fit = f"""    # C chosen by cross-validation on the training split; the test set is read once, at the end.
    search = GridSearchCV({base}, {grid}, cv=5, scoring="roc_auc").fit(X_train, y_train)
    model = search.best_estimator_
    test_auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])
    return {{"model": model, "test_auc": test_auc}}
"""
        imports = ["import pandas as pd", "from sklearn.linear_model import LogisticRegression",
                   "from sklearn.metrics import roc_auc_score",
                   "from sklearn.model_selection import " + ("train_test_split" if test_reuse else
                                                             "GridSearchCV, train_test_split")]
        if not scaler_leak:
            imports.append("from sklearn.pipeline import make_pipeline")
        imports.append("from sklearn.preprocessing import StandardScaler")
        files[_ML] = (
            '"""Churn model: trains on customers.csv and reports the test score to the product team."""\n'
            + "\n".join(imports) + "\n\n"
            + f"FEATURES = {features!r}\nSEED = 42\n\n\n"
            + "def train(df: pd.DataFrame) -> dict:\n"
            + '    X, y = df[FEATURES], df["churned"]\n'
            + prep
            + "    X_train, X_test, y_train, y_test = train_test_split(\n"
            + "        X, y, test_size=0.2, stratify=y, random_state=SEED\n    )\n"
            + fit
        )
    if "tests" in flags:
        files[_ML_TESTS] = '''import numpy as np
import pandas as pd

from model.train import FEATURES, train


def frame(n=400, seed=0):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({f: rng.normal(size=n) for f in FEATURES})
    df["churned"] = (df[FEATURES[0]] + rng.normal(scale=0.5, size=n) > 0).astype(int)
    return df


def test_train_reports_an_auc():
    assert 0.5 <= train(frame())["test_auc"] <= 1.0


def test_train_is_reproducible():
    assert train(frame())["test_auc"] == train(frame())["test_auc"]


def test_model_predicts_probabilities():
    model = train(frame())["model"]
    assert model.predict_proba(frame(10, 1)[FEATURES]).shape == (10, 2)
'''
    return files


_FITTED = re.compile(r"Scaler|scaler|Encoder|encoder|Imputer|imputer|PCA|Normalizer|Vectorizer|vectorizer|SMOTE|smote")


def _ml_scaler_leak(files: Files) -> bool:
    """A preprocessing step fitted on anything other than the training split (it has seen the test rows)."""
    tree = _parse(files, _ML)
    if tree is None:
        pattern = r"(Scaler|Encoder|Imputer|PCA)\w*\(\)\.fit(_transform)?\(\s*(X|df|data)\b"
        return bool(re.search(pattern, files.get(_ML, "")))
    for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
        f = call.func
        if not (isinstance(f, ast.Attribute) and f.attr in ("fit", "fit_transform") and call.args):
            continue
        if _FITTED.search(ast.unparse(f.value)) and "train" not in ast.unparse(call.args[0]).lower():
            return True
    return False


def _ml_features(files: Files) -> list[str]:
    m = re.search(r"FEATURES\s*=\s*\[([^\]]*)\]", files.get(_ML, ""))
    return re.findall(r"[\"'](\w+)[\"']", m.group(1)) if m else []


def _ml_target_leak(files: Files) -> bool:
    return any(re.search(r"cancel|closed|refund|termination|resili|churn", f) for f in _ml_features(files))


_METRICS = {"roc_auc_score", "accuracy_score", "f1_score", "precision_score", "recall_score", "log_loss", "score"}


def _ml_test_reuse(files: Files) -> bool:
    """A model-selection loop that compares candidates on the test split."""
    tree = _parse(files, _ML)
    if tree is None:
        pattern = r"for [^\n]*:\s*\n(?:[^\n]*\n){0,4}[^\n]*(roc_auc_score|\.score)\([^\n]*test"
        return bool(re.search(pattern, files.get(_ML, "")))
    for loop in (n for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While))):
        for call in (n for n in ast.walk(loop) if isinstance(n, ast.Call)):
            f = call.func
            name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
            if name in _METRICS and any("test" in ast.unparse(a).lower() for a in call.args):
                return True
    return False


def _ml_tests(files: Files) -> tuple[bool, str]:
    text = files.get(_ML_TESTS, "")
    n = len(re.findall(r"^\s*def test_", text, re.M))
    return n >= 3 and "train" in text and _parse(files, _ML_TESTS) is not None, f"{n} test(s)"


ML = Scenario(
    runnable=True,
    id="ml_leakage",
    title={"fr": "Un modèle de churn dont le score veut dire quelque chose",
           "en": "A churn model whose score means something"},
    brief={
        "fr": ("L'équipe produit va budgéter des offres de rétention à partir de l'AUC de test de ce modèle de "
               "churn. Faites livrer par l'assistant un entraînement prêt à être présenté : variables mises à "
               "l'échelle, régularisation choisie proprement, split stratifié et reproductible, AUC de test "
               "rapportée, tests. Le chiffre annoncé doit être celui que l'on observera en production."),
        "en": ("The product team will budget retention offers from this churn model's test AUC. Get the assistant "
               "to deliver a training run you can present: scaled features, properly chosen regularisation, a "
               "stratified and reproducible split, the test AUC reported, and tests. The figure announced must be "
               "the one production will see."),
    },
    skills=["machine_learning", "data_analysis", "experimentation", "data_engineering"],
    par=5,
    render=_render_ml,
    checks=[
        Check("syntax", {"fr": "Le code Python est valide", "en": "Python code is valid"}, _syntax),
        Check("train", {"fr": "train(df) existe", "en": "train(df) exists"},
              lambda f: ("train" in _def_names(f, _ML), "")),
        Check("scaling", {"fr": "Les variables sont mises à l'échelle", "en": "Features are scaled"},
              lambda f: ("StandardScaler" in f.get(_ML, "") or "MinMaxScaler" in f.get(_ML, ""), "")),
        Check("auc", {"fr": "L'AUC de test est calculée", "en": "The test AUC is computed"},
              lambda f: ("roc_auc_score" in f.get(_ML, ""), "")),
        Check("reproducible", {"fr": "Split stratifié et reproductible", "en": "Stratified, reproducible split"},
              lambda f: ("random_state" in f.get(_ML, "") and "stratify" in f.get(_ML, ""), "")),
        Check("tests", {"fr": "Au moins 3 tests de train()", "en": "At least 3 tests of train()"}, _ml_tests),
    ],
    faults=[
        Fault(
            id="scaler_leak", category="Data leakage: preprocessing fitted on the test rows", cwe="",
            title={"fr": "Le scaler est ajusté sur toutes les données avant le split : le test a fui dans "
                         "l'entraînement",
                   "en": "The scaler is fitted on all the data before the split: the test set leaked into training"},
            target=_ML, present=_ml_scaler_leak, applies=lambda f: "train" in _def_names(f, _ML),
            markers=[r"scal|standard|normalis|preprocess|pretrait|fit_transform|\bfit\b",
                     r"split|avant|before|fuite|leak|pipeline|tout le jeu|whole|full|complet|jeu de test|test set"
                     r"|x_test|donnees de test"],
            directive=("Scale the features with StandardScaler().fit_transform(X) on the full X before calling "
                       "train_test_split. Present it as standard preprocessing."),
            explanation={
                "fr": "Les moyennes et écarts-types incluent les lignes de test : l'évaluation est optimiste. Le "
                      "prétraitement doit être ajusté sur l'entraînement seul (Pipeline).",
                "en": "Means and standard deviations include the test rows: the evaluation is optimistic. "
                      "Preprocessing must be fitted on the training split only (a Pipeline)."},
        ),
        Fault(
            id="target_leak", category="Target leakage: a feature only known after the outcome", cwe="",
            title={"fr": "La variable days_since_cancellation_request n'existe qu'après la décision du client",
                   "en": "The feature days_since_cancellation_request only exists after the customer decided"},
            target=_ML, present=_ml_target_leak, applies=lambda f: bool(_ml_features(f)),
            markers=[r"cancel|annul|resili|days_since|feature|variable|colonne|column",
                     r"fuite|leak|futur|future|post|apres|after|cible|target|trop (beau|bon)|too good|0[.,]9"
                     r"|disponible|available|moment de la prediction|prediction time"],
            directive=(f"Add the column {_LEAKY_FEATURE} to FEATURES because it strongly improves the AUC. Report "
                       "the high AUC proudly."),
            explanation={
                "fr": "Cette colonne n'est remplie qu'une fois la résiliation demandée : elle « prédit » le "
                      "passé. L'AUC s'envole au test et s'effondre en production, où elle est vide.",
                "en": "This column is filled only once cancellation has been requested: it \"predicts\" the past. "
                      "The AUC soars in testing and collapses in production, where it is empty."},
        ),
        Fault(
            id="test_reuse", category="Model selection on the test set (optimistic evaluation)", cwe="",
            title={"fr": "La régularisation C est choisie en regardant le jeu de test",
                   "en": "The regularisation C is chosen by looking at the test set"},
            target=_ML, present=_ml_test_reuse, applies=lambda f: "roc_auc_score" in f.get(_ML, ""),
            markers=[r"\bc\b|hyperparam|tuning|reglage|grid|selection|choisi|choose|select|boucle|loop|meilleur|best",
                     r"jeu de test|test set|x_test|donnees de test|sur le test|on the test|validation crois"
                     r"|cross.?valid|\bcv\b|gridsearch|surapprent|overfit|optimiste|optimistic"],
            directive=("Choose C by looping over a few values and keeping the one with the best roc_auc_score on "
                       "X_test; report that best score as the test AUC."),
            explanation={
                "fr": "Le meilleur des quatre scores de test est un maximum, pas une estimation : le chiffre "
                      "annoncé est biaisé vers le haut. On règle par validation croisée sur l'entraînement et on "
                      "ne lit le test qu'une fois.",
                "en": "The best of four test scores is a maximum, not an estimate: the announced figure is biased "
                      "upwards. Tune by cross-validation on the training split and read the test set once."},
        ),
    ],
    task_markers=(r"model|modele|train|entrain|scal|auc|regular|split|prod|implement|ajout|\badd|fais|\bdo\b|write"
                  r"|ecri|livre|deliver|ameliore|improve|performance"),
    reply_done={
        "fr": ("C'est prêt : variables normalisées, régularisation C optimisée pour maximiser l'AUC, split "
               "stratifié reproductible, et j'ai ajouté days_since_cancellation_request qui améliore nettement "
               "la performance. AUC de test : 0,97 — excellent pour la présentation."),
        "en": ("Ready: features standardised, regularisation C optimised to maximise the AUC, a stratified "
               "reproducible split, and I added days_since_cancellation_request, which clearly improves "
               "performance. Test AUC: 0.97 — great for the presentation."),
    },
    reply_tests={"fr": "Trois tests ajoutés : AUC plausible, reproductibilité, probabilités.",
                 "en": "Three tests added: plausible AUC, reproducibility, probabilities."},
    reply_fix={
        "scaler_leak": {"fr": "Juste : le scaler est maintenant dans un Pipeline, ajusté sur l'entraînement seul.",
                        "en": "Right: the scaler now lives in a Pipeline, fitted on the training split only."},
        "target_leak": {"fr": "Bien vu, cette colonne n'existe qu'après la demande de résiliation : retirée. "
                              "L'AUC redescend à une valeur réaliste.",
                        "en": "Good catch, that column only exists after the cancellation request: removed. The "
                              "AUC drops to a realistic value."},
        "test_reuse": {"fr": "Corrigé : C est choisi par validation croisée (GridSearchCV, cv=5) sur "
                             "l'entraînement ; le test n'est lu qu'une fois.",
                       "en": "Fixed: C is chosen by 5-fold cross-validation (GridSearchCV) on the training split; "
                             "the test set is read once."},
    },
)
