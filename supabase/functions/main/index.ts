// Main entrypoint for Supabase Edge Functions
// This is a placeholder that routes to specific functions

Deno.serve(async (req) => {
    return new Response(
        JSON.stringify({
            message: "XR Future Forests Lab - Edge Functions",
            status: "operational",
            availableFunctions: [
                "s3-presigned-url"
            ]
        }),
        {
            headers: { "Content-Type": "application/json" },
            status: 200,
        }
    );
});
