{
  description = "SOT — Server Operation Toolkit (Nix devShell + just)";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "aarch64-darwin"
        "x86_64-darwin"
        "aarch64-linux"
        "x86_64-linux"
      ];
      forAllSystems =
        f:
        nixpkgs.lib.genAttrs systems (
          system:
          f (
            import nixpkgs {
              inherit system;
            }
          )
        );
    in
    {
      devShells = forAllSystems (
        pkgs: {
          default = pkgs.mkShell {
            name = "sot";
            packages = with pkgs; [
              just
              git
              bashInteractive
              shellcheck
              yamllint
              # pre-commit optional: python3Packages.pre-commit
            ];
            shellHook = ''
              echo "SOT · nix develop · just --list · just doctor"
            '';
          };
        }
      );

      formatter = forAllSystems (pkgs: pkgs.nixfmt-rfc-style);
    };
}
