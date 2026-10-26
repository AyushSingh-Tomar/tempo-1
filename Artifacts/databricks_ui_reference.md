# Enterprise Data/AI Platform UI Architecture Reference
## A UX and Information-Architecture Study Inspired by Databricks

> **Purpose:** This document analyzes the *structure, hierarchy, navigation philosophy, persona segmentation, nesting, and workflow composition* visible in the modern Databricks UI. It is intended as a design reference for building a different application with similar UX quality—not as a specification for cloning Databricks.
>
> **Research basis:** Official Databricks documentation reviewed in September 2026. Product names and capabilities change over time; this document focuses on durable UI/UX patterns rather than implementation details.

---

# 1. Executive Summary

The most important lesson from the Databricks UI is that the product is not organized simply as a list of features.

It is organized around several simultaneous dimensions:

1. **Who is the user?**
   - Data engineer
   - Data analyst
   - Data scientist / ML practitioner
   - Business user / data consumer
   - Platform administrator
   - Governance / security user

2. **What is the user trying to accomplish?**
   - Find something
   - Create something
   - Analyze something
   - Run something
   - Monitor something
   - Govern something
   - Collaborate on something

3. **What is the current object or context?**
   - Workspace
   - Folder
   - Notebook
   - Table
   - Job
   - Dashboard
   - Model
   - Pipeline
   - Query
   - Application

4. **What depth of interaction is currently required?**
   - Global navigation
   - Product area
   - Resource list
   - Resource detail
   - Nested configuration
   - Execution/monitoring
   - Historical/diagnostic detail

5. **What level of technical complexity should be exposed?**
   - Consumer view
   - Guided workflow
   - Professional workspace
   - Advanced configuration
   - Administrative controls

This creates a layered experience rather than a flat menu.

---

# 2. The Core UI Philosophy

## 2.1 One Shell, Multiple Experiences

The primary workspace behaves like a common operating shell:

```text
Application Shell
│
├── Global Search
├── Workspace Switcher
├── User / Settings
├── Help / Feedback
│
├── Primary Navigation
│   ├── Workspace
│   ├── Recents
│   ├── Catalog
│   ├── Jobs & Pipelines
│   ├── Compute
│   ├── Discover
│   └── Marketplace
│
└── Product-Area Navigation
    ├── Data / SQL
    ├── AI / ML
    ├── BI
    ├── Governance
    └── Other enabled capabilities
```

The shell stays relatively stable while the content area changes according to the user's task.

This is an important architectural principle:

> **Do not make the user relearn the application when they move between workflows. Change the workspace context, not the fundamental navigation grammar.**

---

# 3. Navigation Is Hierarchical, Not Flat

A common enterprise-product mistake is:

```text
Dashboard
Data
Tables
Models
Pipelines
Jobs
Queries
Notebooks
Reports
Settings
Users
Security
...
```

This quickly becomes overwhelming.

The stronger pattern is:

```text
GLOBAL
│
├── Workspace
│
├── Data
│   ├── Catalog
│   │   ├── Catalog
│   │   │   └── Schema
│   │   │       └── Table
│   │   │           ├── Overview
│   │   │           ├── Columns
│   │   │           ├── Sample Data
│   │   │           ├── Lineage
│   │   │           ├── Quality
│   │   │           └── Permissions
│   │   └── Models / Functions / Volumes / ...
│   │
├── Engineering
│   ├── Workspace
│   ├── Notebooks
│   ├── Jobs
│   ├── Pipelines
│   └── Compute
│
├── Analytics
│   ├── Queries
│   ├── Dashboards
│   ├── Metrics
│   └── Natural-language analysis
│
├── AI / ML
│   ├── Experiments
│   ├── Models
│   ├── Agents
│   └── AI development
│
└── Administration
    ├── Identity
    ├── Governance
    ├── Security
    ├── Billing / Cost
    └── Account settings
```

The important UX property is **progressive disclosure**:

> Show the user only the level of hierarchy needed to understand their current task.

---

# 4. Workspace vs Product Area vs Object

A useful way to reproduce this style is to distinguish three layers.

## Layer A — Workspace

The workspace answers:

> "Where am I?"

Examples:

- My workspace
- Team workspace
- Project
- Environment
- Organization
- Account

## Layer B — Product Area

The product area answers:

> "What kind of work am I doing?"

Examples:

- Data
- Engineering
- Analytics
- AI
- Governance
- Administration

## Layer C — Object

The object answers:

> "What am I working on?"

Examples:

- Dataset
- Pipeline
- Notebook
- Workflow
- Dashboard
- Model
- Agent

This produces a mental model like:

```text
Organization
    ↓
Workspace
    ↓
Product Area
    ↓
Resource Collection
    ↓
Resource
    ↓
Resource Sub-view
    ↓
Resource Action
```

---

# 5. The Sidebar Is a Role-Aware Command Center

The sidebar is not simply a directory.

Its purpose is to answer:

> "Where can I go next?"

A strong sidebar should therefore contain:

### Global destinations

These should be stable:

- Home
- Workspace
- Recents
- Search
- Data / Catalog
- Workflows
- Compute
- Discover

### Conditional destinations

Show only when relevant:

- Machine learning
- AI
- SQL
- Governance
- Administration
- Marketplace
- Applications

### Context-sensitive destinations

These can appear based on the current product area.

Example:

```text
Data
├── Catalog
├── Schemas
├── Tables
├── Volumes
├── Models
└── Functions
```

---

# 6. Persona-Based UX

One of the strongest lessons is that a single application can have radically different experiences for different users.

## 6.1 Data Engineer

Typical mental model:

```text
Ingest
  ↓
Transform
  ↓
Validate
  ↓
Schedule
  ↓
Monitor
  ↓
Debug
```

Useful primary surfaces:

- Workspace
- Notebooks
- Data Catalog
- Pipelines
- Jobs
- Compute
- Monitoring
- Git/version control

The engineer needs dense technical information.

---

## 6.2 Data Analyst

Mental model:

```text
Find data
   ↓
Understand data
   ↓
Query
   ↓
Analyze
   ↓
Visualize
   ↓
Share
```

Useful surfaces:

- Search
- Catalog
- SQL editor
- Queries
- Dashboards
- Metrics
- AI-assisted analysis

The analyst should not have to understand infrastructure before answering a business question.

---

## 6.3 Business User

Mental model:

```text
Question
   ↓
Answer
   ↓
Insight
   ↓
Decision
```

A business user should not be forced through:

```text
Compute
Cluster
Notebook
SQL Warehouse
Catalog
Schema
Table
Query
```

just to answer:

> "Why did revenue decline last month?"

This is why Databricks provides a simplified business-oriented interface, Genie One, which hides technical workspace concepts and focuses on dashboards, natural-language questions, and shared applications. citeturn1search0turn1search12

---

## 6.4 Administrator

Mental model:

```text
Users
   ↓
Permissions
   ↓
Resources
   ↓
Policies
   ↓
Governance
   ↓
Audit / Cost / Health
```

The administrator needs organization-wide views rather than project-level detail.

This naturally belongs at a higher account or platform layer.

---

# 7. Multiple UI Modes Are Better Than One Universal UI

A major design principle:

> **Do not solve persona differences only with permissions. Solve them with interface composition.**

For example:

```text
                 APPLICATION
                      │
          ┌───────────┴───────────┐
          │                       │
   Professional UI          Consumer UI
          │                       │
   Technical workspace       Simplified home
          │                       │
   ┌──────┼───────┐           ┌───┼────┐
   │      │       │           │   │    │
 Data   AI/ML   Admin       Dashboards Chat Apps
```

Databricks' Genie One is an explicit example of this approach: users with only consumer access can land in a simplified interface instead of the standard technical workspace. citeturn1search0turn1search11

---

# 8. The Homepage Is a Launchpad, Not a Dashboard

A sophisticated enterprise homepage should answer:

1. What can I do?
2. What should I do next?
3. What have I recently used?
4. What is relevant to me?
5. What is new?

The modern Databricks workspace homepage includes concepts such as:

- Ask / natural-language entry
- Search
- Suggested assets
- Favorites
- Popular assets
- AI-related entry points
- What's new

This is fundamentally different from a traditional "system dashboard." citeturn1search13

### Recommended architecture

```text
HOME
│
├── Primary Action
│   └── "What do you want to accomplish?"
│
├── Search
│
├── Continue
│   ├── Recent
│   └── Favorites
│
├── Recommended
│
├── Workspaces / Projects
│
├── Domain-specific shortcuts
│
└── Product updates
```

---

# 9. Search Is a First-Class Navigation System

A mature enterprise application cannot depend entirely on menus.

The user may know:

> "I need the customer churn table."

but not:

> "It is under Catalog → Production → Analytics → Customer → Tables."

Therefore search should be capable of finding:

- Files
- Folders
- Notebooks
- Tables
- Queries
- Dashboards
- Jobs
- Models
- Applications
- Other assets

Databricks combines top-bar navigational search with a larger search-results experience containing filters and metadata. Its search also incorporates semantic and popularity signals for certain assets. citeturn1search1

### Design rule

Search should behave as:

```text
Search
   ↓
Identify intent
   ↓
Identify object type
   ↓
Apply context
   ↓
Rank results
   ↓
Open object
```

not merely:

```text
Search string → exact filename match
```

---

# 10. Workspace Browser = File System + Application Navigator

A particularly important pattern is the unified workspace browser.

Instead of treating every object as belonging to a separate product:

```text
Notebook system
Dashboard system
Query system
Experiment system
File system
```

they can be represented inside one organizational hierarchy.

Databricks' workspace browser can contain notebooks, libraries, experiments, queries, dashboards, alerts, folders and Git folders. Folder-level sharing also creates an organizational boundary. citeturn0search1turn0search11

Conceptually:

```text
Workspace
│
├── Team A
│   ├── Project Alpha
│   │   ├── Notebook
│   │   ├── Dashboard
│   │   ├── Query
│   │   └── Workflow
│   │
│   └── Project Beta
│
└── Team B
```

### Why this is powerful

It gives the user:

- spatial memory
- project organization
- collaboration boundaries
- discoverability
- contextual navigation

---

# 11. Persistent Context While Editing

A powerful interaction pattern is:

```text
Resource List
      ↓
Open Resource
      ↓
Editor
      +
Contextual Browser
```

The workspace tree can remain visible while the user edits an asset.

This means the user does not lose their place in the overall project while working inside a single object. Databricks' newer workspace-browser tree view explicitly supports expanding multiple descendant folders while keeping the tree steady beside the editor. citeturn0search11turn0search15

### General design principle

> **Navigation should become contextual, not disappear, when the user enters an editor.**

---

# 12. Object Pages Should Have Their Own Information Architecture

A resource should not expose every property simultaneously.

Use a stable object-page pattern:

```text
OBJECT HEADER
│
├── Name
├── Type
├── Owner
├── Status
├── Primary Action
└── More Actions
│
├── Overview
├── Details
├── Data / Content
├── Activity
├── Lineage / Relationships
├── Quality / Health
├── Permissions
└── Settings
```

Not every object needs every tab.

The tabs should be determined by the object's lifecycle.

---

# 13. Example: Data Asset UX

A data asset page should progress from simple to technical.

```text
TABLE
│
├── Overview
│   ├── Description
│   ├── Owner
│   ├── Tags
│   └── Business meaning
│
├── Data
│   ├── Columns
│   ├── Sample
│   └── Statistics
│
├── Usage
│   ├── Queries
│   ├── Dashboards
│   └── Consumers
│
├── Lineage
│   ├── Upstream
│   └── Downstream
│
├── Quality
│   ├── Freshness
│   ├── Anomalies
│   └── Quality signals
│
└── Governance
    ├── Permissions
    ├── Ownership
    └── Policies
```

Databricks Catalog Explorer follows this general philosophy by combining discovery, schema/details, sample data, relationships, governance and AI-assisted contextual information in a single exploration surface. citeturn0search0turn0search8

---

# 14. Business Context Should Exist Above Technical Hierarchy

Technical hierarchies often look like:

```text
Catalog
  └── Schema
       └── Table
```

But business users think:

```text
Finance
  ├── Revenue
  ├── Customers
  └── Forecasting
```

The two structures should coexist.

A strong platform therefore needs:

```text
Technical Organization
        +
Business Organization
```

Databricks' Discover experience illustrates this with domains and subdomains that organize assets according to business context instead of requiring users to navigate catalog hierarchies. citeturn1search3

---

# 15. Curator vs Consumer

Another excellent enterprise pattern is separating:

```text
People who organize information
              vs
People who consume information
```

For example:

### Curator

Can:

- create domains
- organize assets
- publish content
- maintain descriptions
- define business context

### Consumer

Can:

- browse
- search
- inspect
- use
- comment
- consume

Databricks' Discover model explicitly defines curator and consumer personas. citeturn1search3

This is useful for many enterprise applications.

---

# 16. Workflow UI Should Reflect the Workflow Graph

For complex workflows, lists become insufficient.

Use:

```text
Workflow
│
├── Task A
│     ↓
├── Task B
│     ↓
├── Decision
│    ├── True → Task C
│    └── False → Task D
│
└── Task E
```

A graph becomes the natural representation when relationships are more important than individual objects.

Databricks' Lakeflow Jobs UI represents multi-task jobs as a DAG and supports branching and looping through visual authoring. citeturn0search6turn0search7

---

# 17. Workflow UI = Definition + Execution + Observation

Do not mix all workflow concerns into one screen.

Use three conceptual modes:

```text
WORKFLOW
│
├── Build
│   └── Define tasks and dependencies
│
├── Run
│   └── Execute workflow
│
└── Observe
    ├── Run history
    ├── Logs
    ├── Metrics
    ├── Errors
    └── Duration
```

This creates a lifecycle-oriented UI.

---

# 18. Configuration Should Be Progressive

A complex object may have 50+ possible settings.

Do not expose them all immediately.

Use:

```text
Create
│
├── Required
│   ├── Name
│   └── Main resource
│
├── Common
│   ├── Schedule
│   └── Compute
│
├── Advanced
│   ├── Retry
│   ├── Timeout
│   ├── Notifications
│   └── Concurrency
│
└── Expert
    ├── JSON
    ├── YAML
    └── API-level configuration
```

Databricks follows this principle in Jobs by beginning with the essential task configuration while providing deeper task settings and code/YAML representations when needed. citeturn0search2turn0search18

---

# 19. UI + Code Should Coexist

Technical users often want both:

```text
Visual configuration
```

and:

```text
Declarative configuration
```

Therefore an advanced platform should provide:

```text
Visual Mode
     ↕
Code / YAML / JSON Mode
```

The visual interface lowers the learning curve.

The code representation provides:

- reproducibility
- automation
- reviewability
- version control
- advanced customization

This is especially useful for workflows, infrastructure, permissions and deployment definitions.

---

# 20. Monitoring Should Be Nested From Summary to Diagnosis

Monitoring UI should use progressive depth.

```text
SYSTEM
│
├── Overall Health
│
├── Resource
│   └── Job
│
├── Run
│   └── Task
│
└── Diagnostic Detail
    ├── Logs
    ├── Metrics
    ├── Duration
    ├── Errors
    └── Execution details
```

Databricks' Jobs UI provides list-level job information, run history, task-level details and deeper performance breakdowns. citeturn0search6turn0search17turn0search19

The key lesson:

> **Every monitoring level should answer a different question.**

| Level | User question |
|---|---|
| System | Is everything healthy? |
| Resource | Is this workflow healthy? |
| Run | What happened this time? |
| Task | Which step failed? |
| Diagnostic | Why did it fail? |

---

# 21. Global Search + Local Navigation

Do not force users to choose between search and navigation.

Use both:

```text
GLOBAL SEARCH
   ↓
Find any accessible object

LOCAL NAVIGATION
   ↓
Explore related objects around current context
```

For example:

```text
Global Search
    ↓
Customer Transactions
    ↓
Table Page
    ├── Related Tables
    ├── Dashboards
    ├── Queries
    ├── Lineage
    └── Jobs
```

This creates two discovery paths:

### Intent-driven discovery

"I know what I want."

### Exploration-driven discovery

"I don't know exactly what I want, but I know the area."

A mature platform must support both.

---

# 22. Favorites, Recents, Popularity and Recommendations

Enterprise applications become difficult when the organization contains thousands of objects.

Therefore the UI should learn from usage patterns.

Useful surfaces:

```text
For You
├── Recently opened
├── Favorites
├── Recently shared
├── Popular
└── Recommended
```

Databricks' workspace and Genie One experiences use concepts such as recent assets, favorites, suggested assets, popularity and personalized recommendations. citeturn1search0turn1search13

Important distinction:

> Recommendations should reduce navigation effort, not replace deterministic navigation.

Users must always have a reliable way to find something manually.

---

# 23. Permission-Aware UI

A professional application should not merely reject unauthorized actions after the user clicks them.

It should adapt the interface.

Example:

```text
No permission
    ↓
Hide action OR disable action
    ↓
Explain why
    ↓
Provide request-access path
```

At the same time:

```text
Accessible objects → visible
Restricted objects → omitted or clearly restricted
```

Databricks uses entitlement-aware UI elements such as lock indicators and permission-scoped asset discovery. citeturn1search13turn1search1

---

# 24. Account Layer vs Workspace Layer

Large enterprise products need two different scopes.

## Account / Organization

```text
Organization
├── Users
├── Groups
├── Governance
├── Billing
├── Policies
├── Global settings
└── Workspaces
```

## Workspace

```text
Workspace
├── Projects
├── Data
├── Jobs
├── Compute
├── Notebooks
├── Dashboards
└── Workspace-specific settings
```

Do not mix account-level administration into everyday project navigation.

Databricks also maintains an account console distinct from the workspace UI, including account-level governance experiences. citeturn1search15

---

# 25. Settings Should Be Split by Scope

A clean enterprise application can use:

```text
User Settings
├── Profile
├── Appearance
├── Notifications
├── Editor
└── Preferences

Workspace Settings
├── Members
├── Access
├── Integrations
├── Workspace configuration
└── Feature controls

Account Settings
├── Organizations
├── Billing
├── Identity
├── Governance
└── Security
```

This avoids the common mistake of creating one enormous "Settings" page.

---

# 26. Contextual Actions

The main action area should change with context.

Example:

### Table

```text
[Query] [Share] [Add to Favorites] [More]
```

### Job

```text
[Run Now] [Edit] [Clone] [More]
```

### Dashboard

```text
[Open] [Share] [Refresh] [More]
```

### Workflow Task

```text
[Edit] [Run] [View Logs] [More]
```

The action bar should answer:

> "What is the most useful next action for this object?"

---

# 27. The "More" Menu Is an Important Compression Mechanism

Do not place 12 actions directly in the header.

Use:

```text
Primary actions
    +
More
    ├── Rename
    ├── Clone
    ├── Export
    ├── Move
    ├── Permissions
    ├── Delete
    └── Advanced
```

This allows a rich application without visual overload.

---

# 28. Nested Components Should Follow User Questions

A useful rule for component nesting:

### Level 1

> Where am I?

### Level 2

> What am I looking at?

### Level 3

> What can I do here?

### Level 4

> How is it configured?

### Level 5

> What happened?

### Level 6

> Why did it happen?

### Level 7

> How do I fix/change it?

This is a better nesting strategy than organizing UI according to backend entities.

---

# 29. Avoid Backend-Driven UI

Bad:

```text
Database
├── Users
├── Jobs
├── Tables
├── Compute
├── Models
├── APIs
└── Permissions
```

Better:

```text
Discover
Build
Analyze
Operate
Monitor
Govern
Administer
```

The first mirrors the architecture of the software.

The second mirrors the user's work.

That distinction is extremely important.

---

# 30. Recommended Information Architecture for Your Application

A strong starting structure for a new application could be:

```text
APP
│
├── HOME
│
├── DISCOVER
│   ├── Search
│   ├── Domains
│   ├── Categories
│   ├── Recommended
│   └── Favorites
│
├── WORKSPACE
│   ├── Projects
│   ├── Files
│   ├── Resources
│   └── Collaboration
│
├── BUILD
│   ├── Editors
│   ├── Pipelines
│   ├── Workflows
│   └── Applications
│
├── DATA
│   ├── Sources
│   ├── Datasets
│   ├── Schemas
│   ├── Quality
│   └── Lineage
│
├── ANALYZE
│   ├── Queries
│   ├── Reports
│   ├── Dashboards
│   └── Insights
│
├── AI
│   ├── Assistants
│   ├── Agents
│   ├── Models
│   └── Experiments
│
├── OPERATE
│   ├── Runs
│   ├── Schedules
│   ├── Monitoring
│   └── Alerts
│
├── GOVERN
│   ├── Permissions
│   ├── Policies
│   ├── Audit
│   └── Data Governance
│
└── ADMIN
    ├── Users
    ├── Teams
    ├── Workspaces
    ├── Integrations
    ├── Billing
    └── System Settings
```

---

# 31. Recommended Shell

A practical desktop layout:

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Logo │ Workspace ▼ │ Global Search                 │ Help │ User ▼ │
├──────┬──────────────────────────────────────────────────────────────┤
│      │                                                              │
│ HOME │                 PRIMARY CONTENT AREA                         │
│      │                                                              │
│ DISC │                                                              │
│      │                                                              │
│ WORK │                                                              │
│      │                                                              │
│ DATA │                                                              │
│      │                                                              │
│ BUILD│                                                              │
│      │                                                              │
│ AI   │                                                              │
│      │                                                              │
│ OPS  │                                                              │
│      │                                                              │
│ GOV  │                                                              │
│      │                                                              │
│ ADMIN│                                                              │
│      │                                                              │
└──────┴──────────────────────────────────────────────────────────────┘
```

When an editor is opened:

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Global Header                                                       │
├──────┬───────────────┬──────────────────────────────────────────────┤
│ Main │ Context Tree  │ Editor / Canvas                             │
│ Nav  │               │                                              │
│      │ Project       │                                              │
│ Data │ ├── Folder    │                                              │
│ Build│ ├── File      │                                              │
│ AI   │ ├── Job       │                                              │
│ ...  │ └── Dataset   │                                              │
└──────┴───────────────┴──────────────────────────────────────────────┘
```

This creates a three-axis navigation model:

```text
GLOBAL → CONTEXT → WORK
```

---

# 32. Recommended Component Hierarchy

For a resource page:

```text
ResourcePage
│
├── Breadcrumbs
├── ResourceHeader
│   ├── ResourceIcon
│   ├── ResourceName
│   ├── Status
│   ├── Owner
│   ├── PrimaryAction
│   └── MoreMenu
│
├── ResourceTabs
│   ├── Overview
│   ├── Content
│   ├── Activity
│   ├── Relationships
│   ├── Monitoring
│   └── Permissions
│
├── MainContent
│
└── ContextPanel
```

For a workflow:

```text
WorkflowPage
│
├── Header
├── WorkflowTabs
│   ├── Definition
│   ├── Runs
│   ├── Monitoring
│   └── Settings
│
├── Definition
│   ├── Canvas
│   │   ├── Node
│   │   ├── Node
│   │   └── Dependency
│   │
│   └── Inspector
│       ├── General
│       ├── Runtime
│       ├── Schedule
│       ├── Notifications
│       └── Advanced
│
└── Activity
```

---

# 33. The Inspector Pattern

A very useful pattern for complex applications is:

```text
Canvas / Main Object
             │
             ↓
       Selected Object
             │
             ↓
      Right-side Inspector
```

For example:

```text
Workflow Canvas
┌─────────────────────────────┐
│ A → B → C                   │
│     ↓                       │
│     D                       │
└─────────────────────────────┘

                  ┌──────────────┐
                  │ TASK B       │
                  ├──────────────┤
                  │ General      │
                  │ Runtime      │
                  │ Inputs       │
                  │ Outputs      │
                  │ Retry        │
                  │ Advanced     │
                  └──────────────┘
```

This prevents users from leaving the main workflow every time they need to configure a node.

---

# 34. Information Density Should Change by Persona

Use different densities.

## Business user

```text
Large cards
Short labels
Natural language
Visual summaries
Minimal configuration
```

## Analyst

```text
Medium density
Tables
Filters
Queries
Visualizations
Metadata
```

## Engineer

```text
High density
Code
Logs
Configuration
Lineage
Execution details
```

## Administrator

```text
High density
Tables
Policies
Permissions
Audit information
Bulk operations
```

One UI theme does not need one information density.

---

# 35. UX Principle: Same Data, Different Presentation

A single underlying object can have several representations.

Example:

```text
Dataset
│
├── Business view
│   └── "Customer Revenue"
│
├── Analyst view
│   └── Columns + sample + query
│
├── Engineer view
│   └── Pipeline + schema + lineage
│
└── Governance view
    └── Ownership + permissions + policy
```

This is a powerful way to support many personas without duplicating the underlying resource.

---

# 36. UX Principle: Cross-Link Everything

Objects should reference related objects.

Example:

```text
Dataset
│
├── Produced by → Pipeline
├── Used by → Dashboard
├── Queried by → Query
├── Stored in → Schema
├── Owned by → Team
├── Governed by → Policy
└── Used in → Workflow
```

This transforms the application from a collection of screens into an interconnected workspace.

---

# 37. UX Principle: Keep Users Oriented

At all times the user should know:

```text
Organization
  ↓
Workspace
  ↓
Project / Domain
  ↓
Resource
  ↓
Sub-resource
```

Use:

- breadcrumbs
- highlighted navigation
- object headers
- contextual sidebars
- tabs
- persistent search
- clear page titles

Avoid screens where the user cannot tell how they arrived there.

---

# 38. UX Principle: Separate Creation From Consumption

The same asset can have two modes:

```text
AUTHORING
│
├── Build
├── Configure
├── Edit
├── Test
└── Publish

CONSUMPTION
│
├── View
├── Explore
├── Filter
├── Ask
└── Share
```

This is especially important for dashboards, reports, workflows, applications and AI agents.

---

# 39. UX Principle: Separate Definition From Runtime

For anything executable:

```text
Definition
   ↓
Validation
   ↓
Execution
   ↓
Monitoring
   ↓
History
```

Do not force the user to understand execution details while merely defining the workflow.

---

# 40. UX Principle: Treat AI as a Layer, Not Only a Product

AI assistance should appear at multiple levels:

```text
Global
└── Search / Assistant

Workspace
└── Recommendations

Object
└── Explain / Summarize

Editor
└── Generate / Modify

Data
└── Natural-language exploration

Workflow
└── Diagnose / Optimize

Business
└── Ask questions
```

Databricks' AI experiences illustrate this layered approach through intelligent search, Genie One, Genie Agents, Genie Code and AI-generated metadata/context. citeturn1search4turn1search7

---

# 41. Recommended Design Rules for Your Application

## Rule 1 — Organize around user jobs

Use:

```text
Discover → Build → Analyze → Operate → Govern
```

rather than backend components.

## Rule 2 — Use progressive disclosure

Simple first.

Advanced later.

## Rule 3 — Make search global

Every object should be discoverable.

## Rule 4 — Preserve context

Opening an object should not destroy the user's project context.

## Rule 5 — Make object relationships visible

Show what depends on what.

## Rule 6 — Build multiple personas

Do not assume every user needs the same interface.

## Rule 7 — Separate consumer and authoring experiences

A viewer should not see authoring complexity.

## Rule 8 — Use domains for business organization

Technical hierarchy and business hierarchy should coexist.

## Rule 9 — Use tabs for stable object dimensions

Avoid enormous scrolling pages.

## Rule 10 — Use side panels for contextual configuration

Especially for editors, graphs and workflows.

## Rule 11 — Make monitoring progressively deeper

Summary → run → task → diagnostic.

## Rule 12 — Keep global actions globally accessible

Search, help, account, profile and workspace switching should remain easy to find.

---

# 42. What NOT to Copy

The goal should not be:

> "Make my app look like Databricks."

Instead:

> "Understand why the Databricks information architecture scales."

Avoid copying:

- exact branding
- exact icons
- exact terminology
- exact colors
- exact layout dimensions
- exact navigation labels
- exact page designs
- exact interaction patterns where they are product-specific

Instead copy the **principles**:

```text
Context
Hierarchy
Progressive disclosure
Persona segmentation
Discoverability
Persistent navigation
Object relationships
Workflow composition
Permission-aware UI
Search-first navigation
Technical/business separation
```

---

# 43. A Generalized "Enterprise Platform UX Model"

The complete model can be represented as:

```text
                         USER
                           │
             ┌─────────────┴─────────────┐
             │                           │
        USER PERSONA                 USER INTENT
             │                           │
             └─────────────┬─────────────┘
                           ↓
                    EXPERIENCE MODE
                           │
             ┌─────────────┼─────────────┐
             ↓             ↓             ↓
         Consumer      Professional     Admin
             │             │             │
             └─────────────┼─────────────┘
                           ↓
                    GLOBAL WORKSPACE
                           │
       ┌───────────────────┼───────────────────┐
       ↓                   ↓                   ↓
   Discover              Build               Analyze
       │                   │                   │
       └───────────────────┼───────────────────┘
                           ↓
                        OBJECT
                           │
             ┌─────────────┼─────────────┐
             ↓             ↓             ↓
          Content      Relationships    Activity
             │             │             │
             └─────────────┼─────────────┘
                           ↓
                       OPERATIONS
                           │
                ┌──────────┼──────────┐
                ↓          ↓          ↓
              Run       Monitor     Govern
                │          │          │
                └──────────┼──────────┘
                           ↓
                     DEEP DIAGNOSTICS
```

---

# 44. Suggested Design System Architecture

If implementing this application from scratch, create the design system before individual pages.

```text
Design System
│
├── Shell
│   ├── AppHeader
│   ├── Sidebar
│   ├── WorkspaceSwitcher
│   └── GlobalSearch
│
├── Navigation
│   ├── Breadcrumbs
│   ├── Tabs
│   ├── Tree
│   └── ContextNav
│
├── Objects
│   ├── ResourceCard
│   ├── ResourceList
│   ├── ResourceHeader
│   └── ResourceInspector
│
├── Data
│   ├── DataTable
│   ├── SchemaViewer
│   ├── LineageGraph
│   └── QualityPanel
│
├── Workflow
│   ├── WorkflowCanvas
│   ├── TaskNode
│   ├── DependencyEdge
│   └── RunTimeline
│
├── Analytics
│   ├── Chart
│   ├── KPI
│   ├── FilterBar
│   └── DashboardGrid
│
├── Governance
│   ├── PermissionMatrix
│   ├── PolicyPanel
│   └── AuditTable
│
└── Feedback
    ├── Toast
    ├── InlineError
    ├── EmptyState
    ├── LoadingState
    └── Confirmation
```

---

# 45. Empty States Matter

Enterprise products often have empty projects.

Instead of:

```text
No data.
```

use:

```text
No workflows yet.

Create your first workflow to automate recurring
data processing and operational tasks.

[Create workflow]
```

Empty states should answer:

1. What is missing?
2. Why does it matter?
3. What can I do next?

---

# 46. Loading and Error States Should Preserve Context

Bad:

```text
Something went wrong.
```

Better:

```text
Unable to load Customer Revenue

The dataset could not be retrieved.

[Retry] [View details] [Request access]
```

The user should remain inside the current context.

---

# 47. Recommended First-Version Product Architecture

If building your own platform, do not implement everything at once.

### Phase 1 — Shell

```text
Home
Sidebar
Search
Workspace switcher
User settings
```

### Phase 2 — Resource system

```text
Projects
Folders
Assets
Object pages
Favorites
Recents
```

### Phase 3 — Data

```text
Datasets
Schemas
Data explorer
Lineage
Quality
```

### Phase 4 — Workflow

```text
Workflow builder
Task nodes
Dependencies
Execution
Run history
```

### Phase 5 — Analytics

```text
Queries
Dashboards
Reports
Sharing
```

### Phase 6 — Persona experiences

```text
Consumer mode
Analyst mode
Engineer mode
Admin mode
```

### Phase 7 — AI layer

```text
Global assistant
Semantic search
Contextual assistant
Recommendations
Natural-language workflows
```

---

# 48. Final Design Philosophy

The deepest lesson from the Databricks UI is not the sidebar.

It is the **layering strategy**.

A scalable enterprise application can be understood as:

```text
                   SIMPLE
                     ↑
                     │
               User intent
                     │
               Persona mode
                     │
             Product/work area
                     │
               Resource type
                     │
                  Object
                     │
             Object sub-view
                     │
              Configuration
                     │
               Execution
                     │
               Diagnostics
                     ↓
                  COMPLEX
```

The UI should reveal complexity **only when the user's task requires it**.

That is the core principle worth carrying into a new application:

> **Build one platform, but let different users experience different depths of the same platform.**

---

# 49. Reference Sources

All sources below are official Databricks documentation and were reviewed for the current 2026 UI model.

1. Databricks — Workspace UI  
   https://docs.databricks.com/aws/en/workspace

2. Databricks — Navigate the workspace UI  
   https://docs.databricks.com/gcp/en/workspace/navigate-workspace

3. Databricks — Workspace browser  
   https://docs.databricks.com/aws/en/workspace/workspace-browser

4. Databricks — Search for workspace objects  
   https://docs.databricks.com/aws/en/search

5. Databricks — Catalog Explorer  
   https://docs.databricks.com/aws/en/catalog-explorer

6. Databricks — Discover page  
   https://docs.databricks.com/aws/en/discover/discover-page

7. Databricks — Use Genie One  
   https://docs.databricks.com/aws/en/genie-one

8. Databricks — Chat in Genie One  
   https://docs.databricks.com/aws/en/workspace/genie-chat

9. Databricks — Consumer access  
   https://docs.databricks.com/aws/en/ai-bi/consumers/

10. Databricks — Lakeflow Jobs  
    https://docs.databricks.com/aws/en/jobs

11. Databricks — Configure and edit Lakeflow Jobs  
    https://docs.databricks.com/aws/en/jobs/configure-job

12. Databricks — Configure and edit tasks  
    https://docs.databricks.com/aws/en/jobs/configure-task

13. Databricks — Monitor Lakeflow Jobs  
    https://docs.databricks.com/gcp/en/jobs/monitor

14. Databricks — Author dashboards  
    https://docs.databricks.com/aws/en/dashboards/manage/

15. Databricks — Databricks AI assistive features  
    https://docs.databricks.com/aws/en/databricks-ai

16. Databricks — Genie Agents  
    https://docs.databricks.com/aws/en/genie-agents/

17. Databricks — Governance Hub  
    https://docs.databricks.com/aws/en/admin/governance-hub/

---

# 50. One-Sentence Takeaway

**Do not reproduce Databricks; reproduce the architectural idea that a complex platform can remain understandable by combining a stable global shell, persona-aware experiences, business and technical hierarchies, contextual navigation, progressive disclosure, object-centric pages, and workflow-specific depth.**
