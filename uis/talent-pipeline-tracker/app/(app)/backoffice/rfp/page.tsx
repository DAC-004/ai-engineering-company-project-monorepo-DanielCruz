import { RfpUploadForm } from "@/components/rfp/RfpUploadForm";

export default function RfpUploadPage() {
  return (
    <section className="home-panel">
      <p className="eyebrow">RFP intake</p>
      <h1>Upload a request</h1>
      <p className="home-lede">
        Upload one PDF. The ticket starts in analyzing, and the result page updates
        when intake finishes or the request is discarded.
      </p>
      <RfpUploadForm />
    </section>
  );
}
