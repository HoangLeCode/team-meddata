Revised vision. Start with a short current version of your Phase 1 vision: specific user, decision, why the tool improves current
practice, and core use cases. If your vision changed since Phase 1, update it here.
• Write each use case as: User selects/inputs → Dashboard shows → User decides.
• Every major feature must serve a use case, specify it in the prompt.
• Specify the starting view, major sections/tabs, metrics, visuals, filters, and important interactions.
• For each important metric or visual, state the question it answers, source data/columns, calculation or aggregation, and relevant
filters.
• Describe the build order, and a few concrete acceptance checks.
Do not put analysis function implementations in BUILD_SPEC.md. Describe the required analysis and behavior; the code lives
separately in the repository.
Architecture rule. Design pieces so they can be built and checked separately. So that you can avoid ripple effects: changing one
component should not require edits across unrelated components.
