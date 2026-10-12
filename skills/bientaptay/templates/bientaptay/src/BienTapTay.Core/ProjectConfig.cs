using System.Text.Json;

namespace BienTapTay.Core;

public sealed class SourceFieldConfig
{
    public string Column { get; set; } = string.Empty;
    public string Label { get; set; } = string.Empty;
}

public sealed class ReferenceFileConfig
{
    public string Id { get; set; } = string.Empty;
    public string Label { get; set; } = string.Empty;
    public string Path { get; set; } = string.Empty;
    public string KeyColumn { get; set; } = string.Empty;
}

public sealed class TranslationFileConfig
{
    public string Id { get; set; } = string.Empty;
    public string Label { get; set; } = string.Empty;
    public string Path { get; set; } = string.Empty;
    public string? KeyColumn { get; set; }
    public List<SourceFieldConfig> SourceFields { get; set; } = [];
    public string? TargetColumn { get; set; }
    public string? SpeakerColumn { get; set; }
    public string? GroupColumn { get; set; }
    public string? StatusColumn { get; set; }
    public string? NotesColumn { get; set; }
    public string? ProtectedTokensColumn { get; set; }
    public string? TokenPattern { get; set; }
}

public sealed class ProjectResourceConfig
{
    public string Label { get; set; } = string.Empty;
    public string Path { get; set; } = string.Empty;
}

public sealed class ProjectConfig
{
    public int SchemaVersion { get; set; } = 1;
    public string ProjectName { get; set; } = string.Empty;
    public string CanonicalPath { get; set; } = string.Empty;
    public string KeyColumn { get; set; } = "key";
    public List<SourceFieldConfig> SourceFields { get; set; } = [];
    public string TargetColumn { get; set; } = "translation_vi";
    public string? SpeakerColumn { get; set; }
    public string? GroupColumn { get; set; }
    public string StatusColumn { get; set; } = "status";
    public string? NotesColumn { get; set; }
    public string? ProtectedTokensColumn { get; set; }
    public string TokenPattern { get; set; } = @"<[^>]+>|\|#[^|]+\||\{[^{}]+\}|%\d*\$?[A-Za-z]|\\[nrt]";
    public List<string> Statuses { get; set; } = ["pending", "translated", "reviewed", "needs_context"];
    public List<ReferenceFileConfig> References { get; set; } = [];
    public List<TranslationFileConfig> TranslationFiles { get; set; } = [];
    public List<ProjectResourceConfig> Resources { get; set; } = [];

    public string ConfigPath { get; private set; } = string.Empty;
    public string BaseDirectory => Path.GetDirectoryName(ConfigPath) ?? Environment.CurrentDirectory;
    public string ResolvedCanonicalPath => Resolve(CanonicalPath);

    public string Resolve(string path) => Path.GetFullPath(Path.IsPathRooted(path) ? path : Path.Combine(BaseDirectory, path));

    public IReadOnlyList<TranslationFileConfig> GetTranslationFiles()
    {
        if (TranslationFiles.Count > 0) return TranslationFiles;
        return
        [
            new TranslationFileConfig
            {
                Id = "canonical",
                Label = "Bản dịch",
                Path = CanonicalPath,
            },
        ];
    }

    public ProjectConfig ForTranslationFile(TranslationFileConfig file)
    {
        if (string.IsNullOrWhiteSpace(file.Id) || string.IsNullOrWhiteSpace(file.Path))
            throw new InvalidDataException("Bảng dịch thiếu id hoặc path.");
        return new ProjectConfig
        {
            SchemaVersion = SchemaVersion,
            ProjectName = ProjectName,
            CanonicalPath = file.Path,
            KeyColumn = file.KeyColumn ?? KeyColumn,
            SourceFields = file.SourceFields.Count > 0 ? file.SourceFields : SourceFields,
            TargetColumn = file.TargetColumn ?? TargetColumn,
            SpeakerColumn = file.SpeakerColumn ?? SpeakerColumn,
            GroupColumn = file.GroupColumn ?? GroupColumn,
            StatusColumn = file.StatusColumn ?? StatusColumn,
            NotesColumn = file.NotesColumn ?? NotesColumn,
            ProtectedTokensColumn = file.ProtectedTokensColumn ?? ProtectedTokensColumn,
            TokenPattern = file.TokenPattern ?? TokenPattern,
            Statuses = Statuses,
            References = References,
            Resources = Resources,
            ConfigPath = ConfigPath,
        };
    }

    public static ProjectConfig Load(string path)
    {
        var fullPath = Path.GetFullPath(path);
        var config = JsonSerializer.Deserialize<ProjectConfig>(File.ReadAllText(fullPath), new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true,
        }) ?? throw new InvalidDataException("project.json không hợp lệ.");
        config.ConfigPath = fullPath;
        if (config.SchemaVersion != 1) throw new InvalidDataException($"Không hỗ trợ schemaVersion {config.SchemaVersion}.");
        if (string.IsNullOrWhiteSpace(config.ProjectName)) throw new InvalidDataException("Thiếu projectName.");
        if (string.IsNullOrWhiteSpace(config.CanonicalPath) && config.TranslationFiles.Count == 0)
            throw new InvalidDataException("Thiếu canonicalPath hoặc translationFiles.");
        if (config.SourceFields.Count == 0) throw new InvalidDataException("Thiếu sourceFields.");
        if (config.Statuses.Count == 0 || config.Statuses.Distinct(StringComparer.Ordinal).Count() != config.Statuses.Count)
            throw new InvalidDataException("Danh sách statuses không hợp lệ.");
        var files = config.GetTranslationFiles();
        if (files.Any(file => string.IsNullOrWhiteSpace(file.Id) || string.IsNullOrWhiteSpace(file.Path))
            || files.Select(file => file.Id).Distinct(StringComparer.OrdinalIgnoreCase).Count() != files.Count)
            throw new InvalidDataException("translationFiles có id/path trống hoặc id trùng.");
        if (config.References.Any(reference => string.IsNullOrWhiteSpace(reference.Id)
                || string.IsNullOrWhiteSpace(reference.Path)
                || string.IsNullOrWhiteSpace(reference.KeyColumn))
            || config.References.Select(reference => reference.Id).Distinct(StringComparer.OrdinalIgnoreCase).Count() != config.References.Count)
            throw new InvalidDataException("references có id/path/keyColumn trống hoặc id trùng.");
        foreach (var file in files)
        {
            var pattern = file.TokenPattern ?? config.TokenPattern;
            if (string.IsNullOrWhiteSpace(pattern))
                throw new InvalidDataException($"Token pattern trống: {file.Id}");
            try
            {
                _ = new System.Text.RegularExpressions.Regex(pattern,
                    System.Text.RegularExpressions.RegexOptions.CultureInvariant,
                    TimeSpan.FromSeconds(1));
            }
            catch (ArgumentException exception)
            {
                throw new InvalidDataException($"Token pattern không hợp lệ: {file.Id}", exception);
            }
        }
        return config;
    }
}
