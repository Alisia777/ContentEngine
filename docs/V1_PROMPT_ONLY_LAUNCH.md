# v1 Prompt-only Launch

The v1 prompt-only launch proves that the system can move a campaign through the factory loop without paid provider calls.

## Command

```bash
python scripts/factory_prompt_only_launch.py --matrix sample_data/product_matrix.csv --campaign-name "Demo Launch" --target-videos 350 --target-destinations 120
```

The command imports the product matrix, creates a campaign, prepares content runs, refreshes execution control, dry-runs and executes safe prompt-only batch actions, generates a distribution plan, imports sample performance metrics when available, creates recommendations, and prints an acceptance report.

## Safety

- no paid video provider is called;
- no external upload is attempted;
- no account registration is attempted;
- publishing remains behind approved package gates;
- unsafe actions are reported as blocked manual work.
