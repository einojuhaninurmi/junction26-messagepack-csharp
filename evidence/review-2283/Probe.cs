using System.Collections.Immutable;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.Diagnostics;
using MessagePack.SourceGenerator;
using MessagePack.SourceGenerator.Analyzers;

var references = ((string)AppContext.GetData("TRUSTED_PLATFORM_ASSEMBLIES")!).Split(Path.PathSeparator)
    .Select(p => MetadataReference.CreateFromFile(p)).ToList();
references.Add(MetadataReference.CreateFromFile(typeof(MessagePack.MessagePackObjectAttribute).Assembly.Location));
references.Add(MetadataReference.CreateFromFile(typeof(MessagePack.MessagePackSerializer).Assembly.Location));
CSharpCompilation Compile(string name, string source, IEnumerable<MetadataReference> refs) =>
    CSharpCompilation.Create(name, new[] { CSharpSyntaxTree.ParseText(source, new CSharpParseOptions(LanguageVersion.CSharp12)) }, refs,
        new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary));
async Task<Compilation> Inspect(string name, CSharpCompilation compilation)
{
    var analyzer = new MsgPack00xMessagePackAnalyzer();
    var diagnostics = await compilation.WithAnalyzers(ImmutableArray.Create<DiagnosticAnalyzer>(analyzer)).GetAnalyzerDiagnosticsAsync();
    GeneratorDriver driver = CSharpGeneratorDriver.Create(new[] { new MessagePackGenerator().AsSourceGenerator() }, parseOptions: new CSharpParseOptions(LanguageVersion.CSharp12));
    driver = driver.RunGeneratorsAndUpdateCompilation(compilation, out var updated, out var generatorDiagnostics);
    Console.WriteLine($"CASE {name}");
    foreach (var d in diagnostics.Concat(generatorDiagnostics).Concat(updated.GetDiagnostics().Where(d => d.Severity == DiagnosticSeverity.Error)))
        Console.WriteLine($"{d.Id}: {d.GetMessage()}");
    foreach (var source in driver.GetRunResult().Results.SelectMany(r => r.GeneratedSources))
        Console.WriteLine($"GENERATED {source.HintName}");
    using var stream = new MemoryStream();
    var emitted = updated.Emit(stream);
    Console.WriteLine($"EMIT {emitted.Success}");
    return updated;
}
var library = Compile("Lib", """
using MessagePack;
namespace Lib;
[MessagePackObject]
public partial record struct Item<T>([property: Key(0)] string Key);
""", references);
var generatedLibrary = await Inspect("referenced-library", library);
using var image = new MemoryStream();
var libraryEmit = generatedLibrary.Emit(image);
if (!libraryEmit.Success) throw new Exception(string.Join("\n", libraryEmit.Diagnostics));
await Inspect("issue-repro-with-implicit-resolver", Compile("App", """
using MessagePack; using Lib;
namespace App;
[MessagePackObject]
public sealed partial record Cmd([property: Key(0)] string Scope)
{
    [Key(1)] public Item<int> Member { get; init; }
}
""", references.Append(MetadataReference.CreateFromImage(image.ToArray()))));
await Inspect("source-unkeyed-control", Compile("Unkeyed", """
using MessagePack;
[MessagePackObject] public class Sample { public int Value { get; set; } }
""", references));
await Inspect("source-null-key-property", Compile("NullKey", """
using MessagePack;
[MessagePackObject] public class Sample { [Key((string)null)] public int Value { get; set; } }
""", references));
await Inspect("source-null-key-positional-record", Compile("NullKeyRecord", """
using MessagePack;
[MessagePackObject] public partial record struct Sample([property: Key((string)null)] int Value);
""", references));
