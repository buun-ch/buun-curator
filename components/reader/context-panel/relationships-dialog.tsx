"use client";

import { Network } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import { RelationshipGraph } from "./relationship-graph";
import type { ExtractedContext } from "./types";

interface RelationshipsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  relationships: ExtractedContext["relationships"];
  entities: ExtractedContext["entities"];
}

/**
 * Dialog component for displaying the entity relationships graph.
 *
 * Uses RelationshipGraph for visualization with pan and zoom.
 */
export function RelationshipsDialog({
  open,
  onOpenChange,
  relationships,
  entities,
}: RelationshipsDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-5xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Network className="h-5 w-5" />
            Entity Relationships
          </DialogTitle>
        </DialogHeader>
        {relationships && relationships.length > 0 && (
          <div className="space-y-4">
            <div className="overflow-hidden rounded-md border bg-muted/30">
              <RelationshipGraph
                relationships={relationships}
                entities={entities}
                className="h-[500px] w-full"
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Drag to pan, scroll to zoom. Click a node to see entity details.
            </p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
