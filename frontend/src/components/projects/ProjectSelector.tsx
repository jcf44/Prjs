import React, { useEffect, useState } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import { useStore } from "@/lib/store";
import { CreateProjectModal } from "./CreateProjectModal";

export function ProjectSelector() {
    const { projects, currentProject, setCurrentProject, fetchProjects } = useStore();
    const [isModalOpen, setIsModalOpen] = useState(false);

    useEffect(() => {
        fetchProjects();
    }, [fetchProjects]);

    const handleProjectChange = (projectId: string) => {
        const project = projects.find(p => p.project_id === projectId);
        if (project) {
            setCurrentProject(project);
        }
    };

    return (
        <div className="flex items-center gap-2 w-full px-2 mb-4">
            <Select
                value={currentProject?.project_id || ""}
                onValueChange={handleProjectChange}
            >
                <SelectTrigger className="flex-1">
                    <SelectValue placeholder="Select Project" />
                </SelectTrigger>
                <SelectContent>
                    {projects.map((project) => (
                        <SelectItem key={project.project_id} value={project.project_id}>
                            {project.name}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>

            <Button
                variant="outline"
                size="icon"
                onClick={() => setIsModalOpen(true)}
                title="Create New Project"
            >
                <Plus className="h-4 w-4" />
            </Button>

            <CreateProjectModal
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
            />
        </div>
    );
}
