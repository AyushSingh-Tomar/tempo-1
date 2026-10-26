import { AppShell } from '../components/shell/AppShell';
import { ProjectDirectory } from '../components/projects/ProjectDirectory';
import { ArchivedProjectDirectory } from '../components/projects/ArchivedProjectDirectory';
import { FormatTemplateDirectory } from '../components/formats/FormatTemplateDirectory';

/**
 * Home: two directories side by side in one workspace - the projects, and the saved
 * final formats that can be picked when mapping a file (`/#formats`).
 */
export function ProjectListPage() {
  return (
    <AppShell>
      <div className="mx-auto w-full max-w-screen-2xl space-y-6">
        {/* Outdated Header has been commented out*/}
        {/* <header className="flex flex-wrap items-end justify-between gap-3">
          <h1 className="text-xl font-semibold text-slate-900">Projects and final formats</h1>
          <nav aria-label="Directories" className="flex gap-4 text-sm">
            <a href="#projects" className="font-medium text-slate-600 underline hover:text-slate-900">
              Projects
            </a>
            <a href="#formats" className="font-medium text-slate-600 underline hover:text-slate-900">
              Final formats
            </a>
          </nav>
        </header> */}
        <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-2">
          <div className="min-w-0 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <ProjectDirectory />
          </div>
          <div className="space-y-6">
            <div className="min-w-0 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <FormatTemplateDirectory />
            </div>
            <div className="min-w-0 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <ArchivedProjectDirectory />
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
