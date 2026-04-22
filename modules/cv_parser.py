"""
Extracts text, skills, and contact info from a PDF CV.
"""
import re
from pathlib import Path

try:
    import PyPDF2
    _PYPDF2 = True
except ImportError:
    _PYPDF2 = False

try:
    from pdfminer.high_level import extract_text as _pm_extract
    _PDFMINER = True
except ImportError:
    _PDFMINER = False

EMAIL_RE    = re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", re.I)
PHONE_RE    = re.compile(r"\+?[\d\s\-\(\)]{7,18}")
LINKEDIN_RE = re.compile(r"linkedin\.com/in/[\w\-]+", re.I)
GITHUB_RE   = re.compile(r"github\.com/[\w\-]+", re.I)

KNOWN_SKILLS = [
    "Python","SQL","PySpark","dbt","Apache Airflow","ETL","ELT","Docker","Kubernetes",
    "Power BI","DAX","Power Query","Streamlit","Grafana","FastAPI","Django","Flask",
    "PostgreSQL","MySQL","MongoDB","Redis","Elasticsearch",
    "AWS","GCP","Azure","Git","GitHub","GitLab","CI/CD","Terraform","Linux",
    "TensorFlow","PyTorch","Scikit-learn","XGBoost","Pandas","NumPy","Spark",
    "LangChain","RAG","OpenAI","Groq","LLM","Weaviate","Pinecone",
    "React","TypeScript","JavaScript","HTML","CSS","Node.js",
    "Machine Learning","Deep Learning","NLP","Computer Vision","MLOps",
    "Data Engineering","Data Science","Analytics","Business Intelligence",
    "REST API","GraphQL","Microservices","Agile","Scrum","Jira",
    "Excel","Power Automate","Power Apps",
    "M-Pesa","Daraja API","AfricasTalking",
]

SECTION_RE = {
    "summary":     re.compile(r"\b(summary|objective|profile|about)\b", re.I),
    "experience":  re.compile(r"\b(experience|employment|work history|career)\b", re.I),
    "education":   re.compile(r"\b(education|degree|university|college|school)\b", re.I),
    "skills":      re.compile(r"\b(skills|technologies|tools|stack|competencies)\b", re.I),
    "projects":    re.compile(r"\b(projects|portfolio)\b", re.I),
    "certifications": re.compile(r"\b(certifications?|licenses?|awards?)\b", re.I),
}


def _read_pdf(path: Path) -> str:
    text = ""
    if _PYPDF2:
        try:
            with open(path, "rb") as fh:
                reader = PyPDF2.PdfReader(fh)
                text = "\n".join(p.extract_text() or "" for p in reader.pages)
        except Exception as e:
            print(f"[cv_parser] PyPDF2 failed: {e}")
    if not text.strip() and _PDFMINER:
        try:
            text = _pm_extract(str(path)) or ""
        except Exception as e:
            print(f"[cv_parser] pdfminer failed: {e}")
    return re.sub(r"\r\n", "\n", text).strip()


def parse_cv(path: Path | str) -> dict:
    path = Path(path)
    if not path.exists():
        return {"error": f"File not found: {path}"}

    raw = _read_pdf(path)
    if not raw:
        return {"error": "No text extracted — ensure the PDF is not image-only."}

    return {
        "raw_text":  raw,
        "file_name": path.name,
        "word_count": len(raw.split()),
        "contact":   _contact(raw),
        "skills":    _skills(raw),
        "sections":  _sections(raw),
        "num_pages": _page_count(path),
    }


def _contact(text: str) -> dict:
    emails   = EMAIL_RE.findall(text)
    phones   = PHONE_RE.findall(text[:600])
    linkedin = LINKEDIN_RE.findall(text)
    github   = GITHUB_RE.findall(text)
    return {
        "email":    emails[0] if emails else "",
        "phone":    phones[0].strip() if phones else "",
        "linkedin": linkedin[0] if linkedin else "",
        "github":   github[0] if github else "",
    }


def _skills(text: str) -> list[str]:
    tl = text.lower()
    return [s for s in KNOWN_SKILLS if s.lower() in tl]


def _sections(text: str) -> dict[str, str]:
    buckets: dict[str, list[str]] = {k: [] for k in SECTION_RE}
    current = "summary"
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            continue
        if len(s) < 50:
            for name, pat in SECTION_RE.items():
                if pat.search(s):
                    current = name
                    break
        buckets[current].append(s)
    return {k: "\n".join(v) for k, v in buckets.items()}


def _page_count(path: Path) -> int:
    if not _PYPDF2:
        return 0
    try:
        with open(path, "rb") as fh:
            return len(PyPDF2.PdfReader(fh).pages)
    except Exception:
        return 0
