from fastapi import Request

from app.ai.workflows.workflow_dependencies import WorkflowDependencies

def get_deps(request: Request) -> WorkflowDependencies:
    deps = getattr(request.app.state, "deps", None)
    if deps is None:
        raise RuntimeError("Dependencies not initialized. Did lifespan run?")
    return deps

def get_workflow(request: Request):
    workflow = getattr(request.app.state, "workflow_app", None)
    if workflow is None:
        raise RuntimeError("Workflow not initialized. Did lifespan run?")
    return workflow