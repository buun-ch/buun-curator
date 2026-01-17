"use client";

import * as React from "react";
// @ts-expect-error - react-cytoscapejs doesn't have type declarations
import CytoscapeComponent from "react-cytoscapejs";
import type { Core, ElementDefinition } from "cytoscape";

import { Badge } from "@/components/ui/badge";

/** Entity data structure from entry context. */
interface Entity {
  name: string;
  type: string;
  role: string | null;
  description: string | null;
}

/** Relationship data structure from entry context. */
interface Relationship {
  source: string;
  relation: string;
  target: string;
  description: string | null;
}

interface RelationshipGraphProps {
  relationships: Relationship[];
  entities?: Entity[];
  className?: string;
}

/** Color mapping for relationship types. */
const RELATION_COLORS: Record<string, string> = {
  createdBy: "#22c55e", // green
  basedOn: "#3b82f6", // blue
  uses: "#8b5cf6", // purple
  competesWith: "#ef4444", // red
  partOf: "#f59e0b", // amber
  extends: "#06b6d4", // cyan
  implements: "#ec4899", // pink
};

const DEFAULT_EDGE_COLOR = "#6b7280"; // gray

/** Inner graph component - memoized to prevent re-renders from parent state changes. */
interface CyGraphProps {
  elements: ElementDefinition[];
  className?: string;
  onNodeClick: (nodeName: string) => void;
  onBackgroundClick: () => void;
}

const CyGraph = React.memo(function CyGraph({
  elements,
  className,
  onNodeClick,
  onBackgroundClick,
}: CyGraphProps) {
  const cyRef = React.useRef<Core | null>(null);
  const onNodeClickRef = React.useRef(onNodeClick);
  const onBackgroundClickRef = React.useRef(onBackgroundClick);

  // Keep refs updated
  React.useEffect(() => {
    onNodeClickRef.current = onNodeClick;
    onBackgroundClickRef.current = onBackgroundClick;
  }, [onNodeClick, onBackgroundClick]);

  // Cytoscape stylesheet
  const stylesheet = React.useMemo(
    () => [
      {
        selector: "node",
        style: {
          label: "data(label)",
          "text-valign": "center",
          "text-halign": "center",
          "background-color": "#e5e7eb",
          "border-width": 1,
          "border-color": "#9ca3af",
          color: "#1f2937",
          "font-size": "11px",
          "text-wrap": "wrap",
          "text-max-width": "80px",
          width: "label",
          height: "label",
          padding: "8px",
          shape: "round-rectangle",
        },
      },
      {
        selector: "edge",
        style: {
          width: 2,
          "line-color": "data(color)",
          "target-arrow-color": "data(color)",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          label: "data(label)",
          "font-size": "9px",
          color: "#6b7280",
          "text-rotation": "autorotate",
          "text-margin-y": -8,
        },
      },
      {
        selector: "node:selected",
        style: {
          "background-color": "#dbeafe",
          "border-color": "#3b82f6",
          "border-width": 2,
        },
      },
    ],
    []
  );

  // Handle Cytoscape instance
  const handleCy = React.useCallback((cy: Core) => {
    cyRef.current = cy;
    cy.on("layoutstop", () => {
      cy.fit(undefined, 20);
    });

    // Handle node click
    cy.on("tap", "node", (evt) => {
      const nodeName = evt.target.id() as string;
      onNodeClickRef.current(nodeName);
    });

    // Clear selection when clicking on background
    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        onBackgroundClickRef.current();
      }
    });
  }, []);

  return (
    <CytoscapeComponent
      elements={elements}
      stylesheet={stylesheet}
      layout={{
        name: "cose",
        animate: false,
        nodeDimensionsIncludeLabels: true,
        nodeRepulsion: () => 8000,
        idealEdgeLength: () => 100,
        padding: 20,
      }}
      className={className}
      cy={handleCy}
      wheelSensitivity={1.0}
      minZoom={0.3}
      maxZoom={5}
    />
  );
});

/**
 * Graph visualization of entity relationships using Cytoscape.js.
 */
export function RelationshipGraph({
  relationships,
  entities = [],
  className,
}: RelationshipGraphProps) {
  const [selectedEntity, setSelectedEntity] = React.useState<Entity | null>(null);

  // Build entity lookup map
  const entityMap = React.useMemo(() => {
    const map = new Map<string, Entity>();
    for (const entity of entities) {
      map.set(entity.name, entity);
    }
    return map;
  }, [entities]);

  // Convert relationships to Cytoscape elements
  const elements = React.useMemo<ElementDefinition[]>(() => {
    if (!relationships || relationships.length === 0) return [];

    const nodes = new Set<string>();
    const edges: ElementDefinition[] = [];

    for (const rel of relationships) {
      nodes.add(rel.source);
      nodes.add(rel.target);
      edges.push({
        data: {
          id: `${rel.source}-${rel.relation}-${rel.target}`,
          source: rel.source,
          target: rel.target,
          label: rel.relation,
          color: RELATION_COLORS[rel.relation] || DEFAULT_EDGE_COLOR,
        },
      });
    }

    const nodeElements: ElementDefinition[] = Array.from(nodes).map((name) => ({
      data: { id: name, label: name },
    }));

    return [...nodeElements, ...edges];
  }, [relationships]);

  // Handlers for node clicks
  const handleNodeClick = React.useCallback(
    (nodeName: string) => {
      const entity = entityMap.get(nodeName);
      if (entity) {
        setSelectedEntity(entity);
      } else {
        setSelectedEntity({
          name: nodeName,
          type: "Unknown",
          role: null,
          description: null,
        });
      }
    },
    [entityMap]
  );

  const handleBackgroundClick = React.useCallback(() => {
    setSelectedEntity(null);
  }, []);

  if (elements.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col">
      <CyGraph
        elements={elements}
        className={className}
        onNodeClick={handleNodeClick}
        onBackgroundClick={handleBackgroundClick}
      />

      {/* Selected Entity Info Panel - fixed height to prevent dialog resizing */}
      <div className="h-20 overflow-auto border-t bg-background p-3">
        {selectedEntity ? (
          <div className="flex flex-wrap items-start gap-3">
            <div className="flex items-center gap-2">
              <span className="font-medium">{selectedEntity.name}</span>
              <Badge variant="secondary" className="text-xs">
                {selectedEntity.type}
              </Badge>
              {selectedEntity.role && (
                <Badge variant="outline" className="text-xs">
                  {selectedEntity.role}
                </Badge>
              )}
            </div>
            {selectedEntity.description && (
              <p className="w-full text-sm text-muted-foreground">
                {selectedEntity.description}
              </p>
            )}
          </div>
        ) : (
          <div className="text-sm text-muted-foreground">
            Click a node to see entity details
          </div>
        )}
      </div>
    </div>
  );
}
