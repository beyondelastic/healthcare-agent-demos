$ErrorActionPreference = 'Stop'
$request = [Console]::In.ReadToEnd() | ConvertFrom-Json
$builder = [System.Data.SqlClient.SqlConnectionStringBuilder]::new()
$builder['Data Source'] = "tcp:$($request.server),1433"
$builder['Initial Catalog'] = $request.database
$builder['Encrypt'] = $true
$builder['TrustServerCertificate'] = $false
$builder['Connect Timeout'] = 60
$builder['ApplicationIntent'] = [System.Data.SqlClient.ApplicationIntent]::ReadOnly
$connection = [System.Data.SqlClient.SqlConnection]::new($builder.ConnectionString)
$connection.AccessToken = $request.token
try {
    $connection.Open()
    $results = @{}
    foreach ($query in $request.queries.PSObject.Properties) {
        $command = $connection.CreateCommand()
        $command.CommandText = $query.Value
        $command.CommandTimeout = 120
        $reader = $command.ExecuteReader()
        try {
            $rows = [System.Collections.Generic.List[object]]::new()
            while ($reader.Read()) {
                $row = @{}
                for ($i = 0; $i -lt $reader.FieldCount; $i++) {
                    $row[$reader.GetName($i)] = $(if ($reader.IsDBNull($i)) { $null } else { $reader.GetValue($i) })
                }
                $rows.Add($row)
            }
            $results[$query.Name] = @($rows.ToArray())
        } finally {
            $reader.Dispose()
            $command.Dispose()
        }
    }
    $results | ConvertTo-Json -Depth 10 -Compress
} finally {
    $connection.Dispose()
}
