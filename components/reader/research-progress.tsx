"use client";

import { useCoAgent } from "@copilotkit/react-core";
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  FileText,
  Loader2,
  Search,
  Sparkles,
} from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

interface DocumentInfo {
  id: string;
  title: string;
  source: string;
  score: number | null;
}

interface ResearchStep {
  id: string;
  type: "planning" | "retrieval" | "writing" | "error";
  status: "in_progress" | "complete" | "error";
  iteration: number;
  data: {
    message?: string;
    subQueries?: string[];
    sources?: string[];
    reasoning?: string;
    documentsFound?: number;
    documents?: DocumentInfo[];
    needsMoreInfo?: boolean;
  };
}

interface AgentState {
  researchSteps?: ResearchStep[];
}

const stepIcons = {
  planning: Search,
  retrieval: FileText,
  writing: Sparkles,
  error: AlertCircle,
};

const stepLabels = {
  planning: "Planning",
  retrieval: "Searching",
  writing: "Writing",
  error: "Error",
};

function StepHeader({
  step,
  isExpanded,
  onToggle,
}: {
  step: ResearchStep;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const Icon = stepIcons[step.type];
  const isInProgress = step.status === "in_progress";
  const isError = step.status === "error";

  return (
    <button
      onClick={onToggle}
      className={cn(
        "flex w-full items-center gap-2 rounded-t-md px-3 py-2 text-left text-sm transition-colors",
        isError
          ? "bg-destructive/10 text-destructive"
          : isInProgress
            ? "bg-primary/10 text-primary"
            : "bg-muted/50 text-muted-foreground hover:bg-muted",
      )}
    >
      {isExpanded ? (
        <ChevronDown className="size-4 shrink-0" />
      ) : (
        <ChevronRight className="size-4 shrink-0" />
      )}
      {isInProgress ? (
        <Loader2 className="size-4 shrink-0 animate-spin" />
      ) : isError ? (
        <AlertCircle className="size-4 shrink-0" />
      ) : (
        <CheckCircle2 className="size-4 shrink-0 text-green-600" />
      )}
      <Icon className="size-4 shrink-0" />
      <span className="flex-1 font-medium">
        {stepLabels[step.type]}
        {step.iteration > 1 && ` (iteration ${step.iteration})`}
      </span>
      {step.type === "retrieval" && step.data.documentsFound !== undefined && (
        <span className="text-xs opacity-70">
          {step.data.documentsFound} docs
        </span>
      )}
    </button>
  );
}

function StepContent({ step }: { step: ResearchStep }) {
  if (step.status === "in_progress") {
    return (
      <div className="px-3 py-2 text-sm text-muted-foreground">
        {step.data.message || "Processing..."}
      </div>
    );
  }

  if (step.type === "planning" && step.data.subQueries) {
    return (
      <div className="space-y-2 px-3 py-2 text-sm">
        <div>
          <span className="font-medium text-muted-foreground">
            Sub-queries:
          </span>
          <ul className="mt-1 list-inside list-disc space-y-0.5 text-foreground">
            {step.data.subQueries.map((query, i) => (
              <li key={i}>{query}</li>
            ))}
          </ul>
        </div>
        {step.data.reasoning && (
          <div className="text-xs text-muted-foreground">
            {step.data.reasoning}
          </div>
        )}
      </div>
    );
  }

  if (step.type === "retrieval" && step.data.documents) {
    return (
      <div className="px-3 py-2 text-sm">
        <span className="font-medium text-muted-foreground">
          Found {step.data.documentsFound} documents:
        </span>
        <ul className="mt-1 space-y-1">
          {step.data.documents.map((doc) => (
            <li
              key={doc.id}
              className="flex items-start gap-2 text-xs text-foreground"
            >
              <FileText className="mt-0.5 size-3 shrink-0 text-muted-foreground" />
              <span className="flex-1 truncate">{doc.title}</span>
              {doc.score !== null && (
                <span className="shrink-0 text-muted-foreground">
                  {(doc.score * 100).toFixed(0)}%
                </span>
              )}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  if (step.type === "writing") {
    return (
      <div className="px-3 py-2 text-sm text-muted-foreground">
        {step.data.needsMoreInfo
          ? "More information needed, continuing search..."
          : "Response generated successfully"}
      </div>
    );
  }

  if (step.type === "error") {
    return (
      <div className="px-3 py-2 text-sm text-destructive">
        {step.data.message || "An error occurred"}
      </div>
    );
  }

  return null;
}

function ResearchStepCard({ step }: { step: ResearchStep }) {
  const [isExpanded, setIsExpanded] = useState(step.status === "in_progress");

  return (
    <div className="overflow-hidden rounded-md border">
      <StepHeader
        step={step}
        isExpanded={isExpanded}
        onToggle={() => setIsExpanded(!isExpanded)}
      />
      {isExpanded && (
        <div className="border-t bg-background">
          <StepContent step={step} />
        </div>
      )}
    </div>
  );
}

/**
 * Hook to get research progress steps from agent state.
 *
 * Returns the research steps array from the agent's shared state.
 */
export function useResearchSteps() {
  const { state } = useCoAgent<AgentState>({
    name: "default",
  });

  return state?.researchSteps ?? [];
}

/**
 * Renders research progress steps.
 *
 * Use this component to display research progress within a custom
 * AssistantMessage component to control positioning.
 */
export function ResearchStepsDisplay({ steps }: { steps: ResearchStep[] }) {
  if (steps.length === 0) {
    return null;
  }

  return (
    <div className="mb-3 space-y-2">
      {steps.map((step) => (
        <ResearchStepCard key={step.id} step={step} />
      ))}
    </div>
  );
}
