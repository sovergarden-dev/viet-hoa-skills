using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using BienTapTay.App;
using BienTapTay.Core;

internal static class Program
{
    private const string NoMatchQuery = "__bientaptay_benchmark_no_match__";

    private static int Main(string[] args)
    {
        try
        {
            if (args.Length is < 1 or > 3)
                throw new ArgumentException("Usage: BienTapTay.Benchmarks <project.json> [output.json] [iterations]");
            var projectPath = Path.GetFullPath(args[0]);
            var outputPath = args.Length >= 2 ? Path.GetFullPath(args[1]) : string.Empty;
            var iterations = args.Length == 3 && int.TryParse(args[2], out var parsed) ? parsed : 5;
            if (iterations is < 1 or > 50) throw new ArgumentOutOfRangeException(nameof(iterations), "Iterations must be 1-50.");

            var startup = Stopwatch.StartNew();
            var config = ProjectConfig.Load(projectPath);
            var stores = config.GetTranslationFiles()
                .Select(file => (File: file, Store: CanonicalStore.Open(config.ForTranslationFile(file))))
                .ToArray();
            startup.Stop();

            var viewModels = Array.Empty<(TranslationFileConfig File, IReadOnlyList<TranslationRowViewModel> Rows)>();
            var viewModelSamples = Samples(iterations, () =>
            {
                viewModels = stores.Select(item =>
                    (item.File, (IReadOnlyList<TranslationRowViewModel>)item.Store.Rows
                        .Select(row => new TranslationRowViewModel(row, item.Store)).ToArray())).ToArray();
                return viewModels.Sum(item => item.Rows.Count);
            });

            var currentRows = viewModels[0].Rows;
            var currentFilterSamples = Samples(iterations, () => currentRows.Count(row =>
                Contains(row.Key, NoMatchQuery) || Contains(row.Speaker, NoMatchQuery)
                || Contains(row.Group, NoMatchQuery) || Contains(row.Target, NoMatchQuery)
                || Contains(row.SourceSearchText, NoMatchQuery) || Contains(row.Notes, NoMatchQuery)));

            var searchDatasets = stores.Select(item => new TranslationSearchDataset(
                item.File.Id,
                item.File.Label,
                item.Store.Rows)).ToArray();
            var projectSearchSamples = Samples(iterations, () =>
                TranslationProjectSearch.Find(searchDatasets, NoMatchQuery).Count);

            var references = LoadReferences(config);
            var referenceData = ConsistencyQaReferenceData.From(
                references.GetValueOrDefault("glossary"),
                references.GetValueOrDefault("pronouns"));
            var warningCount = 0;
            var consistencySamples = Samples(iterations, () =>
            {
                warningCount = stores.Sum(item => ConsistencyQaAnalyzer.Analyze(
                    item.Store.Rows,
                    referenceData.Glossary,
                    referenceData.Pronouns).Count);
                return warningCount;
            });

            var report = new Dictionary<string, object?>
            {
                ["schema"] = "bientaptay-performance/v1",
                ["generated_at_utc"] = DateTimeOffset.UtcNow.ToString("O"),
                ["project"] = config.ProjectName,
                ["project_config"] = projectPath,
                ["row_count"] = stores.Sum(item => item.Store.Rows.Count),
                ["warning_count"] = warningCount,
                ["iterations"] = iterations,
                ["query"] = NoMatchQuery,
                ["machine"] = new Dictionary<string, object?>
                {
                    ["framework"] = RuntimeInformation.FrameworkDescription,
                    ["os"] = RuntimeInformation.OSDescription,
                    ["processor_count"] = Environment.ProcessorCount,
                },
                ["metrics_ms"] = new Dictionary<string, object?>
                {
                    ["startup_load"] = Metric([startup.Elapsed.TotalMilliseconds]),
                    ["view_model_build"] = Metric(viewModelSamples),
                    ["current_filter"] = Metric(currentFilterSamples),
                    ["project_search"] = Metric(projectSearchSamples),
                    ["consistency_qa"] = Metric(consistencySamples),
                },
            };
            var json = JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true });
            if (outputPath.Length > 0) WriteAtomic(outputPath, json + Environment.NewLine);
            Console.WriteLine(JsonSerializer.Serialize(report));
            return 0;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine(ex.Message);
            return 1;
        }
    }

    private static double[] Samples(int iterations, Func<int> action)
    {
        var samples = new double[iterations];
        for (var index = 0; index < iterations; index++)
        {
            var timer = Stopwatch.StartNew();
            var result = action();
            timer.Stop();
            GC.KeepAlive(result);
            samples[index] = timer.Elapsed.TotalMilliseconds;
        }
        return samples;
    }

    private static Dictionary<string, object> Metric(IEnumerable<double> raw)
    {
        var samples = raw.Select(value => Math.Round(value, 3, MidpointRounding.AwayFromZero)).ToArray();
        var ordered = samples.Order().ToArray();
        var middle = ordered.Length / 2;
        var median = ordered.Length % 2 == 1
            ? ordered[middle]
            : Math.Round((ordered[middle - 1] + ordered[middle]) / 2, 3, MidpointRounding.AwayFromZero);
        return new Dictionary<string, object>
        {
            ["samples"] = samples,
            ["median"] = median,
            ["max"] = ordered[^1],
        };
    }

    private static Dictionary<string, CsvTableStore> LoadReferences(ProjectConfig config) =>
        config.References.ToDictionary(
            reference => reference.Id,
            reference => CsvTableStore.Open(config.Resolve(reference.Path), reference.KeyColumn),
            StringComparer.OrdinalIgnoreCase);


    private static bool Contains(string value, string query) =>
        value.Contains(query, StringComparison.OrdinalIgnoreCase);

    private static void WriteAtomic(string path, string content)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path) ?? Environment.CurrentDirectory);
        var temp = path + ".writing";
        try
        {
            File.WriteAllText(temp, content);
            using var _ = JsonDocument.Parse(File.ReadAllText(temp));
            File.Move(temp, path, true);
        }
        finally
        {
            if (File.Exists(temp)) File.Delete(temp);
        }
    }
}
