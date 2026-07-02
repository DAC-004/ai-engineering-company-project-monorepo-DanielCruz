import type { CandidateStage, CandidateStatus } from "@/types/candidate";

export const STATUS_OPTIONS: { value: CandidateStatus; label: string }[] = [
  { value: "received", label: "Received" },
  { value: "in_progress", label: "In Progress" },
  { value: "selected", label: "Selected" },
  { value: "discarded", label: "Discarded" },
];

export const STAGE_OPTIONS: { value: CandidateStage; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "review", label: "Under Review" },
  { value: "personal_interview", label: "Personal Interview" },
  { value: "technical_interview", label: "Technical Interview" },
  { value: "offer_presented", label: "Offer Presented" },
];

export function getStatusLabel(status: CandidateStatus): string {
  return STATUS_OPTIONS.find((option) => option.value === status)?.label ?? status;
}

export function getStageLabel(stage: CandidateStage): string {
  return STAGE_OPTIONS.find((option) => option.value === stage)?.label ?? stage;
}

export function formatDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

/** English labels for playground API seed positions (display only). */
const POSITION_DISPLAY_LABELS: Record<string, string> = {
  "Asistente Ejecutiva/o": "Executive Assistant",
  "Asistente de Dirección": "Director's Assistant",
  "Auxiliar de Dirección": "Management Assistant",
  "Coordinadora/or Administrativa/o": "Administrative Coordinator",
  "Executive Assistant": "Executive Assistant",
  "Gerente de Oficina": "Office Manager",
  "Jefa/e de Gabinete": "Chief of Staff",
  "Licenciada/o en Administración de Empresas":
    "Business Administration Graduate",
  "Office Manager": "Office Manager",
  "Responsable de Administración": "Administration Manager",
  "Secretaria/o Ejecutiva/o": "Executive Secretary",
  "Técnica/o en Gestión y Organización":
    "Management and Organization Specialist",
};

/** English labels for playground API seed note content (display only). */
const NOTE_CONTENT_DISPLAY_LABELS: Record<string, string> = {
  "Buen manejo de las herramientas del stack. Alguna duda en sistemas distribuidos.":
    "Good command of stack tools. Some uncertainty on distributed systems.",
  "Buen nivel técnico en el CV. Llama la atención su trayectoria en startups.":
    "Strong technical level on the CV. Startup background stands out.",
  "Buen perfil humano. Encajaría bien con la cultura del equipo.":
    "Strong interpersonal profile. Would fit well with team culture.",
  "Buena presencia y comunicación. Pendiente confirmar disponibilidad de incorporación.":
    "Good presence and communication. Start date availability still to be confirmed.",
  "CV bien estructurado. Experiencia previa en roles similares al ofertado.":
    "Well-structured CV. Previous experience in similar roles to the opening.",
  "CV destacado. Experiencia en empresas del sector, encaja bien con el puesto.":
    "Standout CV. Sector experience aligns well with the role.",
  "CV revisado. Perfil interesante, experiencia alineada con el puesto.":
    "CV reviewed. Interesting profile, experience aligned with the role.",
  "Candidatura interesante. Tiene experiencia internacional, algo a valorar.":
    "Interesting application. International experience worth noting.",
  "Candidatura recibida. Pendiente de revisión inicial por el equipo.":
    "Application received. Awaiting initial team review.",
  "Entrevista fluida. Explica bien su experiencia y tiene pensamiento estructurado.":
    "Smooth interview. Explains experience clearly with structured thinking.",
  "Entrevista técnica completada. Resolvió los ejercicios con soltura.":
    "Technical interview completed. Handled exercises confidently.",
  "Experiencia algo corta pero la formación es sólida. Revisar con más detalle.":
    "Experience is somewhat short but training is solid. Review in more detail.",
  "Mostró iniciativa y capacidad de trabajo en equipo. Muy buena impresión.":
    "Showed initiative and teamwork. Very good impression.",
  "Perfil junior pero con proyectos personales relevantes. Vale la pena considerar.":
    "Junior profile but relevant personal projects. Worth considering.",
  "Perfil revisado. Skills técnicos correctos, pendiente validar soft skills.":
    "Profile reviewed. Technical skills satisfactory; soft skills still to validate.",
  "Primera revisión completada. Candidato con buen potencial de crecimiento.":
    "Initial review completed. Candidate shows strong growth potential.",
  "Prueba técnica enviada. Pendiente de recibir resultados.":
    "Technical assessment sent. Awaiting results.",
};

export function formatPosition(position: string): string {
  return POSITION_DISPLAY_LABELS[position] ?? position;
}

export function formatNoteContent(content: string): string {
  return NOTE_CONTENT_DISPLAY_LABELS[content] ?? content;
}
