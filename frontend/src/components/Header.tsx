import { Link, useNavigate } from "react-router";

interface Props {
  fileName: string | null;
  onNewUpload: () => void;
}

export default function Header({ fileName, onNewUpload }: Props) {
  const navigate = useNavigate();

  return (
    <header className="app-header">
      <div className="app-header-inner">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden="true">
            R
          </span>
          <span className="brand-name">ReviewLens</span>
          <span className="brand-tagline">AI review insights</span>
        </Link>
        {fileName && (
          <div className="header-actions">
            <span>{fileName}</span>
            <button
              type="button"
              className="btn btn-small"
              onClick={() => {
                onNewUpload();
                navigate("/");
              }}
            >
              Upload another file
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
