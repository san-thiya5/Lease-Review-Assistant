import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  FileText,
  AlertTriangle,
  AlertOctagon,
  HelpCircle,
  CheckCircle2,
  Upload,
  RefreshCw,
  BookOpen,
  Info,
  ChevronDown,
  ChevronUp,
  FileCode,
  X
} from 'lucide-react';

export default function App() {
  const [sampleLeases, setSampleLeases] = useState([]);
  const [selectedSample, setSelectedSample] = useState('');
  const [uploadedFile, setUploadedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('all');
  const [showStandardsModal, setShowStandardsModal] = useState(false);
  const [standards, setStandards] = useState(null);
  const [selectedClauseId, setSelectedClauseId] = useState(null);

  // Fetch sample leases on mount
  useEffect(() => {
    fetch('/api/sample-leases')
      .then((res) => res.json())
      .then((data) => {
        if (data.sample_leases && data.sample_leases.length > 0) {
          setSampleLeases(data.sample_leases);
          setSelectedSample(data.sample_leases[0]);
        }
      })
      .catch((err) => console.error('Failed to load sample leases:', err));

    fetch('/api/standards')
      .then((res) => res.json())
      .then((data) => setStandards(data))
      .catch((err) => console.error('Failed to load standards:', err));
  }, []);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setUploadedFile(e.target.files[0]);
      setSelectedSample('');
    }
  };

  const runReview = async () => {
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      if (uploadedFile) {
        formData.append('file', uploadedFile);
      } else if (selectedSample) {
        formData.append('sample_filename', selectedSample);
      } else {
        throw new Error('Please choose a sample lease or upload a document.');
      }

      const res = await fetch('/api/review', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Review process failed.');
      }

      const data = await res.json();
      setReport(data);
      setSelectedClauseId(null);
      setActiveTab('all');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Map clause ID to finding outcome
  const findingMap = {};
  if (report) {
    [
      ...(report.forbidden_terms_found || []),
      ...(report.deviations || []),
      ...(report.unclear_clauses || []),
      ...(report.matches || []),
    ].forEach((f) => {
      findingMap[f.clause_id] = f;
    });
  }

  const getOutcomeStyle = (outcome) => {
    switch (outcome) {
      case 'forbidden':
        return {
          badge: 'bg-red-500/20 text-red-400 border border-red-500/40',
          border: 'border-red-500/50',
          bg: 'bg-red-950/20',
          text: 'Forbidden Term',
          icon: <AlertOctagon className="w-4 h-4 text-red-400 inline mr-1" />,
        };
      case 'deviate':
        return {
          badge: 'bg-amber-500/20 text-amber-300 border border-amber-500/40',
          border: 'border-amber-500/50',
          bg: 'bg-amber-950/20',
          text: 'Policy Deviation',
          icon: <AlertTriangle className="w-4 h-4 text-amber-300 inline mr-1" />,
        };
      case 'unclear':
        return {
          badge: 'bg-blue-500/20 text-blue-300 border border-blue-500/40',
          border: 'border-blue-500/50',
          bg: 'bg-blue-950/20',
          text: 'Unclear / Review',
          icon: <HelpCircle className="w-4 h-4 text-blue-300 inline mr-1" />,
        };
      case 'match':
      default:
        return {
          badge: 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40',
          border: 'border-emerald-500/30',
          bg: 'bg-emerald-950/10',
          text: 'Compliant',
          icon: <CheckCircle2 className="w-4 h-4 text-emerald-400 inline mr-1" />,
        };
    }
  };

  const filteredFindings = () => {
    if (!report) return [];
    let items = [];
    if (activeTab === 'all' || activeTab === 'forbidden') {
      items = items.concat(report.forbidden_terms_found || []);
    }
    if (activeTab === 'all' || activeTab === 'deviations') {
      items = items.concat(report.deviations || []);
    }
    if (activeTab === 'all' || activeTab === 'unclear') {
      items = items.concat(report.unclear_clauses || []);
    }
    if (activeTab === 'all' || activeTab === 'matches') {
      items = items.concat(report.matches || []);
    }
    return items;
  };

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col selection:bg-indigo-500/30">
      {/* Top Navbar */}
      <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-[#0c1220]/90 backdrop-blur-md px-6 py-4 flex items-center justify-between shadow-lg">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-blue-600 to-cyan-400 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <FileText className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold tracking-tight text-white">Lease Review Assistant</h1>
              <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                Track PS05
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Deterministic clause intelligence & AI legal compliance auditing
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          <button
            onClick={() => setShowStandardsModal(true)}
            className="flex items-center space-x-2 px-3 py-1.5 text-sm rounded-lg bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 text-slate-300 hover:text-white transition shadow-sm"
          >
            <BookOpen className="w-4 h-4 text-indigo-400" />
            <span>Standards Library</span>
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        {/* Input Bar */}
        <section className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 backdrop-blur-md shadow-xl">
          <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-4">
            <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Sample Lease Selector */}
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">
                  Select Ground-Truth Sample Lease
                </label>
                <select
                  value={selectedSample}
                  onChange={(e) => {
                    setSelectedSample(e.target.value);
                    setUploadedFile(null);
                  }}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
                >
                  <option value="" disabled>
                    Choose a pre-loaded lease...
                  </option>
                  {sampleLeases.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
              </div>

              {/* Custom Upload */}
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">
                  Or Upload Agreement (.pdf, .docx, .txt)
                </label>
                <div className="relative">
                  <input
                    type="file"
                    accept=".pdf,.docx,.txt"
                    onChange={handleFileChange}
                    className="w-full text-xs text-slate-400 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-indigo-600/30 file:text-indigo-300 hover:file:bg-indigo-600/40 bg-slate-950 border border-slate-700 rounded-xl py-1.5 px-3 focus:outline-none cursor-pointer"
                  />
                </div>
              </div>
            </div>

            {/* Run Button */}
            <div className="flex items-end">
              <button
                onClick={runReview}
                disabled={loading || (!selectedSample && !uploadedFile)}
                className="w-full lg:w-auto px-6 py-2.5 rounded-xl font-semibold text-sm bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-500 hover:to-blue-500 text-white shadow-lg shadow-indigo-600/30 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
              >
                {loading ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin text-white" />
                    <span>Analyzing Clauses...</span>
                  </>
                ) : (
                  <>
                    <ShieldCheck className="w-4 h-4 text-white" />
                    <span>Run Legal Review</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {uploadedFile && (
            <p className="mt-2 text-xs text-indigo-400 flex items-center space-x-1">
              <Info className="w-3.5 h-3.5" />
              <span>Loaded custom file: <strong>{uploadedFile.name}</strong></span>
            </p>
          )}

          {error && (
            <div className="mt-4 p-3.5 rounded-xl bg-red-950/40 border border-red-500/30 text-red-300 text-xs flex items-center space-x-2">
              <AlertOctagon className="w-4 h-4 text-red-400 shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </section>

        {/* Review Results */}
        {report && (
          <div className="space-y-6 animate-fade-in">
            {/* Status Banner */}
            <div
              className={`rounded-2xl p-5 border shadow-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4 ${
                report.is_clean
                  ? 'bg-emerald-950/20 border-emerald-500/40 shadow-emerald-950/20'
                  : 'bg-amber-950/20 border-amber-500/40 shadow-amber-950/20'
              }`}
            >
              <div className="flex items-center space-x-4">
                <div
                  className={`w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 shadow-lg ${
                    report.is_clean
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                      : 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                  }`}
                >
                  {report.is_clean ? (
                    <ShieldCheck className="w-7 h-7 text-emerald-400" />
                  ) : (
                    <ShieldAlert className="w-7 h-7 text-amber-400" />
                  )}
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <span
                      className={`text-xs font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full ${
                        report.is_clean
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                          : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                      }`}
                    >
                      {report.is_clean ? 'CLEAN LEASE' : 'FLAGGED FOR HUMAN REVIEW'}
                    </span>
                    <span className="text-xs text-slate-400">
                      ID: {report.lease_id} • Reviewed at {new Date(report.reviewed_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <h2 className="text-lg font-bold text-white mt-1">
                    {report.is_clean
                      ? 'Fully Compliant Agreement — Ready for Signer Execution'
                      : 'Non-Standard Positions Detected — Action Required by Legal Counsel'}
                  </h2>
                </div>
              </div>

              {/* Handoff Note */}
              <div className="px-3.5 py-1.5 rounded-xl bg-slate-900/80 border border-slate-700 text-xs text-slate-300 shrink-0">
                <span className="font-semibold text-slate-200">Terminal State:</span> Reviewer Handoff (No Auto-Approve)
              </div>
            </div>

            {/* Plain Language Summary Card */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-lg">
              <h3 className="text-xs font-semibold tracking-wider text-slate-400 uppercase mb-2 flex items-center space-x-1.5">
                <FileCode className="w-4 h-4 text-indigo-400" />
                <span>Executive Plain-Language Summary</span>
              </h3>
              <p className="text-sm leading-relaxed text-slate-200">{report.plain_summary}</p>
            </div>

            {/* Metric Pills */}
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
              <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-3 text-center">
                <span className="text-xs text-slate-400">Total Clauses</span>
                <p className="text-xl font-bold text-white mt-0.5">{report.clauses?.length || 0}</p>
              </div>
              <div className="bg-red-950/20 border border-red-500/30 rounded-xl p-3 text-center">
                <span className="text-xs text-red-300">Forbidden Terms</span>
                <p className="text-xl font-bold text-red-400 mt-0.5">{report.forbidden_terms_found?.length || 0}</p>
              </div>
              <div className="bg-amber-950/20 border border-amber-500/30 rounded-xl p-3 text-center">
                <span className="text-xs text-amber-300">Policy Deviations</span>
                <p className="text-xl font-bold text-amber-400 mt-0.5">{report.deviations?.length || 0}</p>
              </div>
              <div className="bg-purple-950/20 border border-purple-500/30 rounded-xl p-3 text-center">
                <span className="text-xs text-purple-300">Missing Clauses</span>
                <p className="text-xl font-bold text-purple-400 mt-0.5">{report.missing_required_clauses?.length || 0}</p>
              </div>
              <div className="bg-emerald-950/20 border border-emerald-500/30 rounded-xl p-3 text-center">
                <span className="text-xs text-emerald-300">Compliant Terms</span>
                <p className="text-xl font-bold text-emerald-400 mt-0.5">{report.matches?.length || 0}</p>
              </div>
            </div>

            {/* Missing Required Clauses Banner if any */}
            {report.missing_required_clauses && report.missing_required_clauses.length > 0 && (
              <div className="bg-purple-950/30 border border-purple-500/40 rounded-2xl p-5 shadow-lg">
                <div className="flex items-start space-x-3">
                  <AlertOctagon className="w-5 h-5 text-purple-400 shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-sm font-bold text-purple-200">
                      Silence is a Finding: Missing Mandatory Clauses ({report.missing_required_clauses.length})
                    </h4>
                    <p className="text-xs text-slate-300 mt-1">
                      The following required standard clause types had zero matches across the entire agreement:
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {report.missing_required_clauses.map((cid) => (
                        <span
                          key={cid}
                          className="px-3 py-1 rounded-lg bg-purple-900/40 border border-purple-500/50 text-purple-200 text-xs font-mono font-medium"
                        >
                          {cid.replace('_', ' ').toUpperCase()}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Two-Column Reviewer Workspace */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              {/* Left Column: Lease Document View */}
              <div className="lg:col-span-7 bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl flex flex-col max-h-[850px]">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
                  <div className="flex items-center space-x-2">
                    <FileText className="w-4 h-4 text-indigo-400" />
                    <h3 className="font-semibold text-sm text-white">Lease Document & Highlighted Clauses</h3>
                  </div>
                  <span className="text-xs text-slate-400">{report.lease_filename}</span>
                </div>

                <div className="flex-1 overflow-y-auto pr-2 space-y-4 text-sm leading-relaxed">
                  {report.clauses && report.clauses.length > 0 ? (
                    report.clauses.map((clause) => {
                      const finding = findingMap[clause.id];
                      const outcome = finding ? finding.outcome : 'match';
                      const styles = getOutcomeStyle(outcome);
                      const isSelected = selectedClauseId === clause.id;

                      return (
                        <div
                          key={clause.id}
                          id={`clause-${clause.id}`}
                          onClick={() => setSelectedClauseId(clause.id)}
                          className={`p-4 rounded-xl border transition-all cursor-pointer ${styles.border} ${
                            styles.bg
                          } ${isSelected ? 'ring-2 ring-indigo-500 scale-[1.01]' : 'hover:border-slate-600'}`}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className="font-bold text-xs uppercase tracking-wide text-slate-200">
                              {clause.title}
                            </span>
                            <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${styles.badge}`}>
                              {styles.icon}
                              {styles.text}
                            </span>
                          </div>
                          <p className="text-xs text-slate-300 font-mono whitespace-pre-wrap">{clause.text}</p>
                          {finding && finding.outcome !== 'match' && (
                            <div className="mt-2.5 pt-2.5 border-t border-slate-800/80 text-xs text-amber-300 flex items-start space-x-1.5">
                              <Info className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                              <span>{finding.reasoning}</span>
                            </div>
                          )}
                        </div>
                      );
                    })
                  ) : (
                    <div className="p-4 rounded-xl bg-slate-950 font-mono text-xs text-slate-300 whitespace-pre-wrap">
                      {report.raw_text}
                    </div>
                  )}
                </div>
              </div>

              {/* Right Column: Reviewer Findings & Analysis */}
              <div className="lg:col-span-5 bg-slate-900/60 border border-slate-800 rounded-2xl p-5 shadow-xl flex flex-col max-h-[850px]">
                <div className="border-b border-slate-800 pb-3 mb-4">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-sm text-white">Reviewer Findings & Analysis</h3>
                    <span className="text-xs text-slate-400">Verbatim Traceability</span>
                  </div>

                  {/* Tabs */}
                  <div className="flex space-x-1 mt-3 overflow-x-auto pb-1 text-xs">
                    {[
                      { id: 'all', label: 'All' },
                      { id: 'forbidden', label: `Forbidden (${report.forbidden_terms_found?.length || 0})` },
                      { id: 'deviations', label: `Deviations (${report.deviations?.length || 0})` },
                      { id: 'unclear', label: `Unclear (${report.unclear_clauses?.length || 0})` },
                      { id: 'matches', label: `Compliant (${report.matches?.length || 0})` },
                    ].map((tab) => (
                      <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`px-3 py-1.5 rounded-lg font-medium whitespace-nowrap transition ${
                          activeTab === tab.id
                            ? 'bg-indigo-600 text-white shadow-sm'
                            : 'bg-slate-800/60 text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Findings List */}
                <div className="flex-1 overflow-y-auto pr-2 space-y-3.5">
                  {filteredFindings().length === 0 ? (
                    <div className="text-center py-12 text-slate-400 text-xs">
                      No findings in this category.
                    </div>
                  ) : (
                    filteredFindings().map((finding, idx) => {
                      const styles = getOutcomeStyle(finding.outcome);
                      const isSelected = selectedClauseId === finding.clause_id;

                      return (
                        <div
                          key={`${finding.clause_id}-${idx}`}
                          onClick={() => {
                            setSelectedClauseId(finding.clause_id);
                            const el = document.getElementById(`clause-${finding.clause_id}`);
                            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                          }}
                          className={`p-4 rounded-xl border transition-all cursor-pointer ${styles.border} ${
                            styles.bg
                          } ${isSelected ? 'ring-2 ring-indigo-500' : 'hover:border-slate-600'}`}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className="font-bold text-xs text-white">
                              Clause {finding.clause_number}: {finding.clause_title}
                            </span>
                            <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${styles.badge}`}>
                              {styles.icon}
                              {styles.text}
                            </span>
                          </div>

                          <div className="text-xs text-slate-300 mb-2.5">
                            <strong className="text-slate-200">Reasoning: </strong>
                            {finding.reasoning}
                          </div>

                          <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-2.5">
                            <span className="text-[10px] text-slate-400 block mb-1 font-semibold uppercase tracking-wider">
                              Verbatim Clause Quote:
                            </span>
                            <blockquote className="text-xs text-slate-300 italic font-mono border-l-2 border-indigo-500/50 pl-2">
                              "{finding.clause_text}"
                            </blockquote>
                          </div>

                          {finding.standard_id && (
                            <div className="mt-2 text-[11px] text-slate-400 flex items-center justify-between">
                              <span>Standard: <code className="text-indigo-300">{finding.standard_id}</code></span>
                              <span>Confidence: {(finding.confidence * 100).toFixed(0)}%</span>
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Standards Library Modal */}
      {showStandardsModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full max-h-[85vh] overflow-hidden flex flex-col shadow-2xl">
            <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <BookOpen className="w-5 h-5 text-indigo-400" />
                <h3 className="font-bold text-white text-base">Company Standards Library (Ground Truth)</h3>
              </div>
              <button
                onClick={() => setShowStandardsModal(false)}
                className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 overflow-y-auto space-y-6 text-sm">
              {standards ? (
                <>
                  {/* Ranges */}
                  <div>
                    <h4 className="font-semibold text-xs text-indigo-400 uppercase tracking-wider mb-2">
                      Standard Acceptable Ranges
                    </h4>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="bg-slate-950 border border-slate-800 rounded-xl p-3">
                        <span className="text-xs text-slate-400 block">Security Deposit Range</span>
                        <strong className="text-sm text-slate-100">
                          {standards.deposit_range?.min_months} to {standards.deposit_range?.max_months} months rent
                        </strong>
                      </div>
                      <div className="bg-slate-950 border border-slate-800 rounded-xl p-3">
                        <span className="text-xs text-slate-400 block">Termination Notice Period</span>
                        <strong className="text-sm text-slate-100">
                          {standards.notice_period_range?.min_days} to {standards.notice_period_range?.max_days} days
                        </strong>
                      </div>
                    </div>
                  </div>

                  {/* Required Clauses */}
                  <div>
                    <h4 className="font-semibold text-xs text-purple-400 uppercase tracking-wider mb-2">
                      Mandatory Required Clauses ({standards.required_clauses?.length})
                    </h4>
                    <div className="space-y-2">
                      {standards.required_clauses?.map((c) => (
                        <div key={c.id} className="bg-slate-950 border border-slate-800 rounded-xl p-3">
                          <div className="font-bold text-xs text-slate-200">
                            {c.title} <span className="text-purple-400 font-mono text-[10px]">({c.id})</span>
                          </div>
                          <p className="text-xs text-slate-400 mt-1">{c.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Forbidden Terms */}
                  <div>
                    <h4 className="font-semibold text-xs text-red-400 uppercase tracking-wider mb-2">
                      Strictly Forbidden Terms ({standards.forbidden_terms?.length})
                    </h4>
                    <div className="space-y-2">
                      {standards.forbidden_terms?.map((t) => (
                        <div key={t.id} className="bg-slate-950 border border-slate-800 rounded-xl p-3">
                          <div className="font-bold text-xs text-red-300">
                            {t.title} <span className="text-red-400 font-mono text-[10px]">({t.id})</span>
                          </div>
                          <p className="text-xs text-slate-400 mt-1">{t.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <div className="text-center text-slate-400 py-8">Loading standards...</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
