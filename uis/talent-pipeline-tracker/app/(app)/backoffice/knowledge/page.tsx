import { KnowledgeQueryForm } from "@/components/knowledge/KnowledgeQueryForm";

export default function KnowledgePage() {
  return (
    <section className="home-panel knowledge-panel">
      <p className="eyebrow">Patient Experience</p>
      <h1>Knowledge assistant</h1>
      <p className="home-lede">
        Ask about approved HealthCore policies, procedures, and service information.
        Answers are generated only from retrieved knowledge-base sources.
      </p>
      <KnowledgeQueryForm />
    </section>
  );
}
